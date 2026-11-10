"""Business rules for #20 Sponsor & Reward Commitment Management.

Rules:
- Only administrators register and manage sponsors, rewards and commitments.
- A sponsor can view (not edit) their own rewards and commitments.
- A commitment's end date cannot be before its start date, and quantity must be at least 1.
- Adding a commitment adds its quantity to the reward's stock. Removing one takes it back,
  but never below zero (units already redeemed cannot be "un-committed").
"""
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Reward, RewardCommitment, RewardStatus, Role, Sponsor
from app.services import auth_service
from app.services import validation as v
from app.services.validation import ServiceError

# ---------- Sponsors ----------


def list_sponsors(db: Session) -> list[Sponsor]:
    stmt = (
        select(Sponsor)
        .options(selectinload(Sponsor.rewards).selectinload(Reward.commitments))
        .order_by(Sponsor.organization_name)
    )
    return list(db.scalars(stmt))


def get_sponsor(db: Session, sponsor_id: int) -> Sponsor | None:
    return db.get(Sponsor, sponsor_id)


def register_sponsor(
    db: Session, *, organization_name: str, contact_person: str, name: str, email: str, phone: str,
    password: str, confirm_password: str,
) -> Sponsor:
    if password != confirm_password:
        raise ServiceError("The two passwords do not match.")
    return auth_service.register_user(
        db, role=Role.SPONSOR, name=name, email=email, password=password, phone=phone,
        profile={"organization_name": organization_name, "contact_person": contact_person},
    )


def update_sponsor(
    db: Session, sponsor: Sponsor, *, organization_name: str, contact_person: str, name: str, phone: str,
    is_active: bool,
) -> Sponsor:
    sponsor.organization_name = v.text(organization_name, "Organisation name", max_len=150)
    sponsor.contact_person = v.text(contact_person, "Contact person", required=False, max_len=100)
    sponsor.name = v.text(name, "Account holder name", max_len=100)
    sponsor.phone = v.text(phone, "Phone", required=False, max_len=20)
    sponsor.is_active = is_active
    db.commit()
    return sponsor


def sponsor_totals(sponsor: Sponsor) -> dict[str, int]:
    return {
        "rewards": len(sponsor.rewards),
        "committed": sum(r.committed_total for r in sponsor.rewards),
        "in_stock": sum(r.stock_quantity for r in sponsor.rewards),
        "available": sum(1 for r in sponsor.rewards if r.is_available()),
    }


# ---------- Rewards ----------


def get_reward(db: Session, reward_id: int) -> Reward | None:
    return db.get(Reward, reward_id)


def save_reward(
    db: Session, sponsor: Sponsor, reward: Reward | None, *, name: str, description: str, points_cost: str,
    status: str,
) -> Reward:
    name = v.text(name, "Reward name", max_len=120)
    description = v.text(description, "Description", required=False, max_len=2000)
    cost = v.integer(points_cost, "Points cost", min_value=1, max_value=1_000_000)
    status = v.choice(status or RewardStatus.ACTIVE, "Status", list(RewardStatus))

    for other in sponsor.rewards:
        if other is not reward and other.name.lower() == name.lower():
            raise ServiceError(f"{sponsor.organization_name} already has a reward called '{name}'.")

    if reward is None:
        reward = Reward(stock_quantity=0)
        sponsor.rewards.append(reward)
    reward.name, reward.description, reward.points_cost, reward.status = name, description, cost, status
    db.commit()
    return reward


def delete_reward(db: Session, reward: Reward) -> None:
    db.delete(reward)  # its commitments go with it (composition)
    db.commit()


# ---------- Commitments ----------


def add_commitment(
    db: Session, reward: Reward, *, quantity: str, valid_from: str, valid_until: str, note: str,
) -> RewardCommitment:
    qty = v.integer(quantity, "Quantity", min_value=1, max_value=1_000_000)
    start = v.date_value(valid_from, "Valid from")
    end = v.date_value(valid_until, "Valid until")
    if end < start:
        raise ServiceError("'Valid until' cannot be before 'Valid from'.")
    note = v.text(note, "Note", required=False)

    commitment = RewardCommitment(quantity=qty, valid_from=start, valid_until=end, note=note)
    reward.commitments.append(commitment)
    reward.stock_quantity += qty
    if reward.status == RewardStatus.EXPIRED and commitment.state() != "expired":
        reward.status = RewardStatus.ACTIVE.value  # new valid supply revives an expired reward
    db.commit()
    return commitment


def delete_commitment(db: Session, reward: Reward, commitment_id: int) -> None:
    commitment = next((c for c in reward.commitments if c.id == commitment_id), None)
    if commitment is None:
        raise ServiceError("That commitment does not exist.")
    if commitment.quantity > reward.stock_quantity:
        raise ServiceError(
            f"Only {reward.stock_quantity} unit(s) are still in stock, so this commitment of "
            f"{commitment.quantity} cannot be removed (some were already redeemed)."
        )
    reward.stock_quantity -= commitment.quantity
    reward.commitments.remove(commitment)
    db.commit()
