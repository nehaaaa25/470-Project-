"""Feature #20: Sponsor & Reward Commitment Management."""
from datetime import date, timedelta

from sqlalchemy import select

from app.models import Reward, RewardCommitment, Role, Sponsor
from tests.conftest import PASSWORD, login

TODAY = date.today()


def _register_sponsor(client, email="green@test.com", org="GreenLeaf"):
    return client.post("/sponsors/new", data={
        "organization_name": org, "contact_person": "Nadia", "name": "Nadia Rahman", "email": email,
        "phone": "", "password": PASSWORD, "confirm_password": PASSWORD,
    })


def _add_reward(client, sponsor_id, name="Jute bag", cost="150", status="active"):
    return client.post(f"/sponsors/{sponsor_id}/rewards/new",
                       data={"name": name, "description": "", "points_cost": cost, "status": status})


def _commit(client, sponsor_id, reward_id, qty="50", start=TODAY, end=TODAY + timedelta(days=30)):
    return client.post(f"/sponsors/{sponsor_id}/rewards/{reward_id}/commitments",
                       data={"quantity": qty, "valid_from": str(start), "valid_until": str(end), "note": ""})


def _setup(client, db):
    _register_sponsor(client)
    sponsor_id = db.scalar(select(Sponsor.id))
    _add_reward(client, sponsor_id)
    reward_id = db.scalar(select(Reward.id))
    return sponsor_id, reward_id


def test_register_sponsor_reward_and_commitment(client, db, as_role):
    as_role(Role.ADMINISTRATOR)
    r = _register_sponsor(client)
    assert "Sponsor &#39;GreenLeaf&#39; registered" in r.text
    sponsor_id = db.scalar(select(Sponsor.id))

    assert "Reward &#39;Jute bag&#39; added" in _add_reward(client, sponsor_id).text
    reward_id = db.scalar(select(Reward.id))
    assert "Commitment of 50 added" in _commit(client, sponsor_id, reward_id).text

    db.expire_all()
    reward = db.get(Reward, reward_id)
    assert reward.stock_quantity == 50 and reward.committed_total == 50 and reward.is_available()
    page = client.get("/sponsors").text
    assert "GreenLeaf" in page


def test_commitment_rules(client, db, as_role):
    as_role(Role.ADMINISTRATOR)
    sponsor_id, reward_id = _setup(client, db)
    assert "cannot be before" in _commit(client, sponsor_id, reward_id, end=TODAY - timedelta(days=1)).text
    assert "at least 1" in _commit(client, sponsor_id, reward_id, qty="0").text
    assert "valid date" in client.post(f"/sponsors/{sponsor_id}/rewards/{reward_id}/commitments",
                                       data={"quantity": "5", "valid_from": "soon", "valid_until": ""}).text
    assert db.scalar(select(RewardCommitment.id)) is None

    _commit(client, sponsor_id, reward_id, qty="10")
    _commit(client, sponsor_id, reward_id, qty="5")
    reward = db.get(Reward, reward_id)
    db.refresh(reward)
    assert reward.stock_quantity == 15

    # Simulate 8 units already redeemed (Reward Shop, feature #16): stock 15 -> 7
    reward.decrease_stock(8)
    db.commit()
    ten, five = sorted(reward.commitments, key=lambda c: c.quantity, reverse=True)
    r = client.post(f"/sponsors/{sponsor_id}/rewards/{reward_id}/commitments/{ten.id}/delete")
    assert "cannot be removed" in r.text  # 10 > 7 left: stock would go negative
    r = client.post(f"/sponsors/{sponsor_id}/rewards/{reward_id}/commitments/{five.id}/delete")
    assert "Commitment removed" in r.text
    db.expire_all()
    assert db.get(Reward, reward_id).stock_quantity == 2


def test_availability(db, make_user):
    sponsor = make_user(Role.SPONSOR)
    reward = Reward(name="Bag", points_cost=10, stock_quantity=5)
    reward.commitments = [RewardCommitment(quantity=5, valid_from=TODAY - timedelta(days=10),
                                           valid_until=TODAY - timedelta(days=1))]
    sponsor.rewards.append(reward)
    db.commit()
    assert not reward.is_available()  # commitment expired
    reward.commitments[0].valid_until = TODAY
    assert reward.is_available()
    reward.status = "paused"
    assert not reward.is_available()


def test_reward_validation(client, db, as_role):
    as_role(Role.ADMINISTRATOR)
    sponsor_id, _ = _setup(client, db)
    assert "already has a reward" in _add_reward(client, sponsor_id, name="JUTE BAG").text
    assert "Points cost must be at least 1" in _add_reward(client, sponsor_id, name="Pen", cost="0").text
    assert "valid status" in _add_reward(client, sponsor_id, name="Pen", status="free").text


def test_sponsor_sees_only_own_page(client, db, as_role):
    as_role(Role.ADMINISTRATOR)
    sponsor_id, reward_id = _setup(client, db)
    _commit(client, sponsor_id, reward_id)
    _register_sponsor(client, email="other@test.com", org="Other Org")
    other_id = db.scalar(select(Sponsor.id).where(Sponsor.email == "other@test.com"))

    login(client, "green@test.com")
    r = client.get("/sponsors")
    assert r.url.path == f"/sponsors/{sponsor_id}" and "Jute bag" in r.text and "Add reward" not in r.text
    assert client.get(f"/sponsors/{other_id}").status_code == 403
    assert _add_reward(client, sponsor_id, name="Hack").status_code == 403
    assert _commit(client, sponsor_id, reward_id).status_code == 403

    as_role(Role.RESIDENT)
    assert client.get("/sponsors").status_code == 403


def test_reward_belongs_to_sponsor_in_url(client, db, as_role):
    as_role(Role.ADMINISTRATOR)
    sponsor_id, reward_id = _setup(client, db)
    _register_sponsor(client, email="other@test.com", org="Other Org")
    other_id = db.scalar(select(Sponsor.id).where(Sponsor.email == "other@test.com"))
    assert client.get(f"/sponsors/{other_id}/rewards/{reward_id}/edit").status_code == 404


def test_deactivate_and_delete_reward(client, db, as_role):
    as_role(Role.ADMINISTRATOR)
    sponsor_id, reward_id = _setup(client, db)
    _commit(client, sponsor_id, reward_id)
    client.post(f"/sponsors/{sponsor_id}/edit", data={"organization_name": "GreenLeaf Ltd", "name": "Nadia"})
    db.expire_all()
    assert db.get(Sponsor, sponsor_id).is_active is False

    client.post(f"/sponsors/{sponsor_id}/rewards/{reward_id}/delete")
    db.expire_all()
    assert db.get(Reward, reward_id) is None and db.scalar(select(RewardCommitment.id)) is None
