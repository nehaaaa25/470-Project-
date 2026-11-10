"""Feature #20: Sponsor & Reward Commitment Management (owner: Rifa)

Class diagram:
    Sponsor 1 ---- * Reward 1 ◆---- * RewardCommitment

A commitment is the sponsor's promise to supply `quantity` units of a reward
between valid_from and valid_until. Adding a commitment adds to the reward's
stock; the Reward Shop (#16) will later take stock away as residents redeem.
"""
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import Sponsor


class RewardStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"


class Reward(Base):
    __tablename__ = "rewards"

    id: Mapped[int] = mapped_column(primary_key=True)
    sponsor_id: Mapped[int] = mapped_column(ForeignKey("sponsors.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    points_cost: Mapped[int] = mapped_column(Integer)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=RewardStatus.ACTIVE.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    sponsor: Mapped[Sponsor] = relationship(back_populates="rewards")
    commitments: Mapped[list["RewardCommitment"]] = relationship(
        back_populates="reward", cascade="all, delete-orphan", order_by="RewardCommitment.valid_from"
    )

    def is_available(self, today: date | None = None) -> bool:
        """Can residents redeem it right now? Needs stock, active status and a valid commitment."""
        today = today or date.today()
        return (
            self.status == RewardStatus.ACTIVE
            and self.stock_quantity > 0
            and any(c.is_valid(today) for c in self.commitments)
        )

    def decrease_stock(self, amount: int = 1) -> None:
        if amount > self.stock_quantity:
            raise ValueError("Not enough stock.")
        self.stock_quantity -= amount

    @property
    def committed_total(self) -> int:
        return sum(c.quantity for c in self.commitments)


class RewardCommitment(Base):
    __tablename__ = "reward_commitments"

    id: Mapped[int] = mapped_column(primary_key=True)
    reward_id: Mapped[int] = mapped_column(ForeignKey("rewards.id", ondelete="CASCADE"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    reward: Mapped[Reward] = relationship(back_populates="commitments")

    def is_valid(self, today: date | None = None) -> bool:
        today = today or date.today()
        return self.valid_from <= today <= self.valid_until

    def state(self, today: date | None = None) -> str:
        today = today or date.today()
        if today < self.valid_from:
            return "upcoming"
        return "valid" if today <= self.valid_until else "expired"


Sponsor.rewards = relationship(Reward, back_populates="sponsor", order_by=Reward.name, cascade="all, delete-orphan")
