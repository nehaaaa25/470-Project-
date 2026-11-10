"""The 5 Sprint-1 features: who owns each one, where it lives and who can open it.

Used by the navbar, home page and dashboard.
`roles` = the account types that can open the feature (None = everyone, even logged-out visitors).
"""
FEATURES = [
    {
        "no": 4, "title": "Waste Sorting Guide & Material Catalogue", "short": "Sorting Guide", "owner": "Neha",
        "url": "/materials", "icon": "recycle", "roles": None,
        "blurb": "Search materials, see which bin they go in and how to prepare them.",
    },
    {
        "no": 10, "title": "Collector & Service Zone Management", "short": "Zones & Collectors", "owner": "Esha",
        "url": "/zones", "icon": "geo-alt", "roles": ("manager", "administrator"),
        "blurb": "Register collectors and assign them to service zones.",
    },
    {
        "no": 14, "title": "Collection Centre Management", "short": "Centres", "owner": "Nowrin",
        "url": "/centres", "icon": "building", "roles": None,
        "blurb": "Find centres, their accepted materials, capacity and opening hours.",
    },
    {
        "no": 20, "title": "Sponsor & Reward Commitment Management", "short": "Sponsors", "owner": "Rifa",
        "url": "/sponsors", "icon": "gift", "roles": ("administrator", "sponsor"),
        "blurb": "Register sponsors and track the rewards they commit to provide.",
    },
    {
        "no": 5, "title": "Special Item Collection Requests", "short": "Special Items", "owner": "Neha",
        "url": "/special-items", "icon": "box-seam", "roles": ("resident", "manager", "administrator"),
        "blurb": "Request help with bulky, electronic or hazardous items.",
    },
]


def get_feature(no: int) -> dict:
    return next(f for f in FEATURES if f["no"] == no)


def can_open(feature: dict, user) -> bool:
    return feature["roles"] is None or (user is not None and user.role in feature["roles"])
