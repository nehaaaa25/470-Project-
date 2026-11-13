# EcoWaste (CSE470)

FastAPI + MySQL web app with an MVC structure. The pages use Jinja2 templates styled with Bootstrap 5.

## Folder map (MVC)

| Layer | Folder | What goes there |
|---|---|---|
| **Model** | `app/models/` | SQLAlchemy classes; each one is a MySQL table |
| **View** | `app/templates/` | Jinja2 + Bootstrap HTML pages |
| **Controller** | `app/routers/` | URL handlers that read forms, call services and render views |
| Services | `app/services/` | Business rules, so controllers stay thin |
| Static | `app/static/` | CSS and JS |
| Migrations | `alembic/versions/` | Changes to the database structure |
| Tests | `tests/` | Automated tests (run on a throwaway SQLite database) |

Shared pieces you will reuse:
- `app/dependencies.py` gives you `DbSession`, `LoggedInUser`, `CurrentUser`, `AdminUser`, `StaffUser` (manager or admin), `require_roles(Role.MANAGER, ...)` and `found(obj)` (shows the 404 page when obj is None).
- `app/templating.py` gives you `render(request, "page.html", {...})` and `flash(request, "Saved!")`.
- `app/services/validation.py` turns form text into clean values or raises `ServiceError` with a friendly message.
- `app/templates/_macros.html` has form helpers: `input`, `textarea`, `checkbox`, `select`, `multi_check`, `post_button`, and more.

## Sprint 1 features (done)

| # | Feature | Owner | URL | Files |
|---|---|---|---|---|
| 4 | Waste Sorting Guide & Material Catalogue | Neha | `/materials` | `models/material.py`, `services/material_service.py`, `routers/materials.py`, `templates/materials/` |
| 10 | Collector & Service Zone Management | Esha | `/zones` | `models/zone.py`, `services/zone_service.py`, `routers/zones.py`, `templates/zones/` |
| 14 | Collection Centre Management | Nowrin | `/centres` | `models/centre.py`, `services/centre_service.py`, `routers/centres.py`, `templates/centres/` |
| 20 | Sponsor & Reward Commitment Management | Rifa | `/sponsors` | `models/reward.py`, `services/reward_service.py`, `routers/sponsors.py`, `templates/sponsors/` |
| 5 | Special Item Collection Requests | Neha | `/special-items` | `models/special_item.py`, `services/special_item_service.py`, `routers/special_items.py`, `templates/special_items/` |

### Who can do what

| Feature | Visitors & everyone | Resident | Collector | Sponsor | Manager | Administrator |
|---|---|---|---|---|---|---|
| #4 Sorting guide | Browse and search | ✓ + AI photo scan | ✓ + AI photo scan | ✓ + AI photo scan | ✓ + AI photo scan | + manage categories, steps, bin types |
| #10 Zones | — | — | Sees own zones on dashboard | — | Manage zones, register/manage collectors | Same as manager |
| #14 Centres | Browse active centres, filter by material | ✓ | ✓ | ✓ | ✓ | + register, edit, deactivate, delete; sees inactive |
| #20 Sponsors | — | — | — | Views own rewards and commitments | — | Register/manage sponsors, rewards, commitments |
| #5 Special items | — | Submit, track, cancel own requests | — | — | Review (approve + refer / reject), manage specialist services | Same as manager |

### Main business rules
- **#4 AI waste scanner** (`/materials/scan`, any logged-in user): the user takes or uploads a photo; Google Gemini picks **one category from our own guide** (or "unknown"), and the page shows that category's bin, biodegradable/recyclable status and preparation steps from the database. The AI never writes the advice itself. Photos are checked like special-item photos, sent to Gemini and **not stored**. Login is required so visitors cannot use up the free AI quota. Code: `services/waste_scan_service.py`; tests fake the AI, so they run offline.
- **#4:** names are unique (case-insensitive); each material has a biodegradable flag set by the admin; non-recyclable materials earn 0 points; steps are numbered 1..n and renumber after a delete; a bin type in use cannot be deleted; deleting a category deletes its steps (composition).
- **#10:** unique zone names; collectors are created by staff (no self-registration); an inactive collector cannot log in; deleting a zone keeps its collectors.
- **#14:** capacity must be > 0; at least one accepted material; latitude and longitude are both given or both empty; inactive centres are hidden from the public.
- **#20:** commitment end date ≥ start date and quantity ≥ 1; each commitment adds to the reward's stock; removing one can never make stock negative; a reward is redeemable only if active, in stock and covered by a currently valid commitment.
- **#5:** only pending requests can be reviewed or cancelled; approval needs an active specialist service of the same item type; rejection needs a reason; residents only see their own requests and photos; photos are checked by file signature (JPG/PNG/WEBP, ≤ 5 MB) and stored outside `static/`.

## First-time setup (each team member)

1. Install Python 3.12 and MySQL 8.4.
2. In this folder:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   copy .env.example .env
   ```
3. Open `.env` and set `DB_PASSWORD` and a random `SECRET_KEY`. You can generate the key with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
   For the AI waste scanner, also set `GEMINI_API_KEY` (free key from https://aistudio.google.com/apikey). Without it the rest of the app works and the scanner page explains what is missing.
4. Create the MySQL database and app user. The script asks for the MySQL **root** password (hidden):
   ```bash
   python -m scripts.setup_mysql
   ```
   Wait for "Check passed".
5. Create the tables, then add sample data and demo accounts:
   ```bash
   alembic upgrade head
   python -m scripts.seed_demo --demo-users
   ```
   Or make your own admin account with `python -m scripts.create_user`.
6. Run the app:
   ```bash
   uvicorn app.main:app --reload
   ```
   Open http://127.0.0.1:8000. The page http://127.0.0.1:8000/health shows whether MySQL is reachable.

### Demo accounts (from `seed_demo --demo-users`)

Password for all of them: `Demo@12345`. They are for local demos only; never create them on a real server.

| Role | Email |
|---|---|
| Administrator | admin@ecowaste.test |
| Manager | manager@ecowaste.test |
| Resident | resident@ecowaste.test |
| Collector | collector@ecowaste.test, collector2@ecowaste.test |
| Sponsor | sponsor@ecowaste.test |

## Tests

```bash
python -m pytest
```
The tests create a fresh SQLite database for each test, so they never touch MySQL. They cover login/logout and registration, access rules per role, the business rules of all 5 features, and that the Alembic migrations create exactly the tables in the models.

## Adding a feature (the usual loop)

1. Write the model in `app/models/<name>.py`, then import it in `app/models/__init__.py`.
2. Run `alembic revision --autogenerate -m "add <name>"`, check the generated file, then run `alembic upgrade head`.
3. Put the business rules in `app/services/<name>_service.py`.
4. Write the URLs in `app/routers/<name>.py` and register the router in `app/main.py`.
5. Add the pages in `app/templates/<name>/` and extend `base.html`. Add the feature to `app/features.py` so it shows in the navbar and dashboard.
6. Add tests in `tests/test_<name>.py`.

Commit the migration file together with the model change, so teammates only need to run `alembic upgrade head`.

## Accounts and roles

`User` is abstract. Each role is a subclass with its own table (joined-table inheritance), matching the class diagram: Resident, Collector, CentreStaff, Recycler, Sponsor, Manager, Administrator.
- **Public Register page:** Resident, Recycler, Sponsor.
- **Staff accounts:** created with `python -m scripts.create_user`. Administrators can also register collectors (`/zones`) and sponsors (`/sponsors`) from the website.
