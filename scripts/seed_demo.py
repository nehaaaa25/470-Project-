"""Fill the database with sample data for the 5 features, so the pages are not empty in a demo.

Run from the project folder (with .venv active), after `alembic upgrade head`:
    python -m scripts.seed_demo                 # sample bins, materials, zones, centres, services
    python -m scripts.seed_demo --demo-users    # ...plus one demo account per role (see DEMO_USERS)

Safe to run again: anything that already exists (same name / email) is skipped.
"""
import sys
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    BinType,
    CollectionCentre,
    Collector,
    MaterialCategory,
    PreparationInstruction,
    Reward,
    RewardCommitment,
    Role,
    ServiceZone,
    SpecialistService,
    Sponsor,
    User,
)
from app.services.auth_service import register_user

DEMO_PASSWORD = "Demo@12345"
DEMO_USERS = [
    # role, name, email, profile
    (Role.ADMINISTRATOR, "Demo Admin", "admin@ecowaste.test", {"admin_level": "1"}),
    (Role.MANAGER, "Demo Manager", "manager@ecowaste.test", {"employee_code": "MGR-01"}),
    (Role.RESIDENT, "Demo Resident", "resident@ecowaste.test", {"address": "House 12, Road 5, Mohakhali, Dhaka"}),
    (Role.COLLECTOR, "Rahim Uddin", "collector@ecowaste.test", {"vehicle_no": "DHA-KA-11-2233"}),
    (Role.COLLECTOR, "Karim Mia", "collector2@ecowaste.test", {"vehicle_no": "DHA-KA-14-7788"}),
    (Role.SPONSOR, "Nadia Rahman", "sponsor@ecowaste.test", {"organization_name": "GreenLeaf Superstore",
                                                              "contact_person": "Nadia Rahman"}),
]

BINS = [
    ("Blue bin", "#1e6fd9", "Clean, dry paper and cardboard"),
    ("Yellow bin", "#f2c200", "Plastic bottles, containers and metal cans"),
    ("Green bin", "#2e7d4f", "Food scraps and garden waste (organic)"),
    ("Grey bin", "#6c757d", "Residual waste that cannot be recycled"),
    ("Red box", "#c62828", "Special handling: e-waste, batteries, hazardous items. Never mix with other bins"),
]

# name, bin, recyclable, points/kg, examples, description, steps
MATERIALS = [
    ("Paper & Cardboard", "Blue bin", True, 5, "newspaper, cereal boxes, egg cartons, office paper",
     "Dry paper and cardboard can be recycled into new paper products.",
     ["Remove plastic wrap and tape", "Flatten boxes to save space", "Keep it dry. Wet or greasy paper goes in the grey bin"]),
    ("Plastic Bottles (PET)", "Yellow bin", True, 8, "water bottles, soft drink bottles, cooking oil bottles",
     "Clear PET bottles are the most valuable household plastic.",
     ["Empty the bottle completely", "Rinse with a little water", "Crush the bottle and put the cap back on"]),
    ("Metal Cans", "Yellow bin", True, 10, "drink cans, food tins, aerosol cans (empty)",
     "Aluminium and steel cans can be recycled again and again.",
     ["Empty and rinse", "Do not crush aerosol cans", "Put lids inside the can"]),
    ("Glass Bottles & Jars", "Yellow bin", True, 3, "sauce jars, juice bottles",
     "Glass is fully recyclable. Broken window glass and mirrors are not accepted.",
     ["Rinse out food", "Remove metal lids (they go with metal cans)", "Do not break the glass"]),
    ("Food & Garden Waste", "Green bin", True, 2, "vegetable peels, rice, tea leaves, leaves, flowers",
     "Organic waste is composted. Keep plastic bags out of it.",
     ["Drain liquids", "Remove stickers and plastic bags", "Wrap in newspaper if wet"]),
    ("Soiled & Mixed Waste", "Grey bin", False, 0, "used tissues, diapers, chip packets, greasy pizza boxes",
     "Items that cannot be recycled. Keep this bin as small as possible.",
     ["Bag it securely"]),
    ("Electronic Waste", "Red box", True, 15, "old phones, chargers, laptops, cables",
     "E-waste contains valuable metals and toxic parts. Request a special collection for big items.",
     ["Delete your personal data", "Remove batteries if you can do it safely", "Keep cables bundled together"]),
    ("Batteries", "Red box", False, 0, "AA/AAA batteries, power banks, phone batteries",
     "Batteries can leak or catch fire. Never put them in a normal bin.",
     ["Tape over the terminals", "Store in a dry box until drop-off"]),
]

ZONES = [
    ("Mohakhali", "Mohakhali DOHS, Wireless Gate, TB Gate area"),
    ("Gulshan-1", "Gulshan Circle-1, Roads 1-30"),
    ("Banani", "Banani Blocks A-H, Kamal Ataturk Avenue"),
]

# name, address, hours, capacity, lat, lng, phone, materials
CENTRES = [
    ("Mohakhali Recycling Hub", "Plot 7, Mohakhali C/A, Dhaka", "Sat-Thu 9:00-17:00", 2500, 23.7781, 90.4057,
     "01700-000001", ["Paper & Cardboard", "Plastic Bottles (PET)", "Metal Cans", "Glass Bottles & Jars"]),
    ("Gulshan Green Point", "Road 32, Gulshan-1, Dhaka", "Daily 8:00-20:00", 800, 23.7806, 90.4167,
     "01700-000002", ["Paper & Cardboard", "Plastic Bottles (PET)", "Food & Garden Waste"]),
    ("Dhaka E-Waste Centre", "Tejgaon Industrial Area, Dhaka", "Sun-Thu 10:00-16:00", 400, 23.7639, 90.3973,
     "01700-000003", ["Electronic Waste", "Batteries", "Metal Cans"]),
]

# name, type, phone, email, notes
SERVICES = [
    ("BulkAway Movers", "bulky", "01800-111111", "hello@bulkaway.test", "Furniture and large appliance removal"),
    ("E-Cycle Bangladesh", "electronic", "01800-222222", "pickup@ecycle.test", "Certified e-waste recycler"),
    ("SafeHaz Disposal", "hazardous", "01800-333333", None, "Licensed hazardous waste handler"),
]


def _by_name(db: Session, model, name: str):
    return db.scalar(select(model).where(model.name == name))


def seed_reference_data(db: Session) -> None:
    for name, colour, desc in BINS:
        if not _by_name(db, BinType, name):
            db.add(BinType(name=name, colour=colour, description=desc))
    db.flush()

    for name, bin_name, recyclable, points, examples, desc, steps in MATERIALS:
        if not _by_name(db, MaterialCategory, name):
            category = MaterialCategory(
                name=name, is_recyclable=recyclable, points_per_kg=points, examples=examples, description=desc,
                bin_type=_by_name(db, BinType, bin_name),
            )
            category.instructions = [PreparationInstruction(step_no=i, instruction=s) for i, s in enumerate(steps, 1)]
            db.add(category)
    db.flush()

    for name, area in ZONES:
        if not _by_name(db, ServiceZone, name):
            db.add(ServiceZone(name=name, area_description=area))

    for name, address, hours, cap, lat, lng, phone, materials in CENTRES:
        if not _by_name(db, CollectionCentre, name):
            db.add(CollectionCentre(
                name=name, address=address, opening_hours=hours, processing_capacity_kg=cap, latitude=lat,
                longitude=lng, phone=phone, materials=[_by_name(db, MaterialCategory, m) for m in materials],
            ))

    for name, stype, phone, email, notes in SERVICES:
        if not _by_name(db, SpecialistService, name):
            db.add(SpecialistService(name=name, service_type=stype, contact_phone=phone, email=email, notes=notes))
    db.commit()


def seed_demo_users(db: Session) -> None:
    for role, name, email, profile in DEMO_USERS:
        if db.scalar(select(User).where(User.email == email)) is None:
            register_user(db, role=role, name=name, email=email, password=DEMO_PASSWORD, profile=profile)
            print(f"  created {role.label:<14} {email}")

    # Give the demo collectors zones, and the demo sponsor a reward with a commitment.
    zones = {z.name: z for z in db.scalars(select(ServiceZone))}
    for email, zone_names in (("collector@ecowaste.test", ["Mohakhali", "Banani"]),
                              ("collector2@ecowaste.test", ["Gulshan-1"])):
        collector = db.scalar(select(Collector).where(Collector.email == email))
        if collector and not collector.zones:
            collector.zones = [zones[n] for n in zone_names if n in zones]

    sponsor = db.scalar(select(Sponsor).where(Sponsor.email == "sponsor@ecowaste.test"))
    if sponsor and not sponsor.rewards:
        reward = Reward(name="Reusable jute shopping bag", description="Handmade jute bag from a local cooperative.",
                        points_cost=150, stock_quantity=50)
        reward.commitments = [RewardCommitment(quantity=50, valid_from=date.today(),
                                               valid_until=date.today() + timedelta(days=90),
                                               note="Quarterly sponsorship")]
        sponsor.rewards.append(reward)
    db.commit()


def main() -> int:
    with SessionLocal() as db:
        seed_reference_data(db)
        print("Sample bins, materials, zones, centres and specialist services are in place.")
        if "--demo-users" in sys.argv:
            seed_demo_users(db)
            print(f"Demo accounts ready. Password for all of them: {DEMO_PASSWORD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
