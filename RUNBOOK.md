# CivicView Runbook

Short checklist to get the platform running (dev or production).

## 1. Environment variables

Create a `.env` file in the project root (see `.env.example` or README). Required:

- `SECRET_KEY` – Django secret
- `DEBUG` – `True` for dev
- `ALLOWED_HOSTS` – e.g. `127.0.0.1,localhost`
- `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_HOST`, `DATABASE_PORT` – PostgreSQL + PostGIS
- `REDIS_URL` or `CELERY_BROKER_URL` – Redis URL (e.g. `redis://localhost:6379/0`)
- `CORS_ALLOWED_ORIGINS` – frontend origin (e.g. `http://127.0.0.1:3000,http://localhost:3000`)

**Windows:** Set `GDAL_LIBRARY_PATH` and `GEOS_LIBRARY_PATH` in `civicview_project/settings.py` to your Conda env paths if needed.

## 2. Start Redis

Required for Celery (hotspot regeneration, async tasks).

```bash
# Linux/macOS
redis-server
# or: sudo systemctl start redis

# Windows: run redis-server from install dir or use Docker
docker run -d -p 6379:6379 redis:7
```

Check: `redis-cli ping` → `PONG`.

## 3. Start Celery worker

From project root with the correct env activated:

```bash
conda activate civicview   # or your venv
celery -A civicview_project worker -l info
```

Keep this running. Hotspot regeneration (on new reports or from the dashboard lab) uses this worker.

## 4. Import boundaries (once per env)

Load county and Dáil constituency geometries for geographic analysis and “My area” filters:

```bash
python manage.py import_boundaries
```

Optional: `--counties path/to/counties.geojson --constituencies path/to/constituencies.geojson` (default paths may be in the command help). Use `--clear` to replace existing boundaries.

## 5. Run Django

```bash
python manage.py runserver
```

API: `http://127.0.0.1:8000/api/`  
Admin: `http://127.0.0.1:8000/admin/`

## 6. Run frontend (dev)

```bash
cd frontend
npm install
npm run dev
```

Open the URL shown (e.g. `http://localhost:3000`). Ensure CORS in `.env` includes this origin.

## Quick checklist

- [ ] Redis running
- [ ] Celery worker running
- [ ] `.env` configured (DB, Redis, CORS)
- [ ] Migrations applied: `python manage.py migrate`
- [ ] Boundaries imported: `python manage.py import_boundaries`
- [ ] Django server running
- [ ] Frontend dev server running (for dev)

## Optional: generate hotspots

After reports exist:

```bash
python manage.py generate_hotspots
```

Or use the **Lab** tab in the dashboard (staff/manager/admin) to run regeneration with custom parameters.
