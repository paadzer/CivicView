# Civic View

Civic View is a GeoDjango-powered civic issue reporting platform for Ireland. It exposes a REST API, runs DBSCAN-based hotspot clustering with Celery, provides geographic analytics (county, Dáil constituency, and local council), and includes a React + Leaflet frontend with dashboard and advanced analytics routes.

## Architecture Overview

- **Presentation layer**: React + Leaflet (`frontend/`)
- **Application layer**: Django REST Framework (`civicview/`)
- **Data layer**: PostgreSQL + PostGIS
- **Processing layer**: Celery + Redis + DBSCAN (scikit-learn)

### Features

- **6-tier role model**: Token auth with register/login and role-based permissions: citizen, moderator, staff, council, manager, admin.
- **Reporting workflow**: Create reports with geolocation, status workflow (open/in_progress/resolved/dismissed), assignment, validation flag, and image uploads.
- **Spatial analytics boundaries**: County, Dáil constituency, and local council entities with comparison and drill-down APIs.
- **Boundary import pipeline**: `import_boundaries` command imports/updates GeoJSON boundaries into PostGIS.
- **Hotspot processing**: DBSCAN clustering via Celery task (`generate_hotspots`) with polygon simplification and nearby-border merge logic.
- **Dashboards**: Management dashboard plus dedicated advanced analytics route (`/advanced-analytics`) backed by `/api/analytics/advanced/`.

## Prerequisites

- **Conda** (or Mamba/Micromamba) - Required for managing Python environment and GeoDjango dependencies
- **PostgreSQL** with **PostGIS** extension installed
- **Redis** server
- **Node.js** and **npm** (for the React frontend)
- **Docker** (optional, for containerized deployment)

### Installing Prerequisites

#### PostgreSQL with PostGIS

**Windows:**
1. Download and install PostgreSQL from [postgresql.org](https://www.postgresql.org/download/windows/)
2. Install PostGIS extension using Stack Builder or via pgAdmin

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib postgis postgresql-postgis
```

**macOS (Homebrew):**
```bash
brew install postgresql postgis
```

#### Redis

**Windows:**
- Download from [redis.io](https://redis.io/download) or use WSL
- Or use Docker: `docker run -d -p 6379:6379 redis:7`

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

**macOS (Homebrew):**
```bash
brew install redis
brew services start redis
```

## Setup

### Step 1: Clone the Repository

```bash
git clone <repo_url> civicview
cd civicview
```

### Step 2: Install Python Dependencies

Use one of the options below.

**Option A (recommended, pip/venv):**
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
pip install -r requirements.txt
```

**Option B (Conda):**
```bash
conda env create -f environment-local.yml
conda activate civicview
pip install -r requirements.txt
```

### Step 3: Create PostgreSQL Database

Create a new PostgreSQL database with PostGIS extension:

**Using psql command line:**
```bash
psql -U postgres
```

Then in the psql prompt:
```sql
CREATE DATABASE civicview;
\c civicview
CREATE EXTENSION postgis;
\q
```

**Using pgAdmin:**
1. Open pgAdmin and connect to your PostgreSQL server
2. Right-click on "Databases" → Create → Database
3. Name it `civicview`
4. Open the database, go to Extensions
5. Enable the `postgis` extension

### Step 4: Configure Environment Variables

Create a `.env` file in the project root directory:

```bash
# Windows
copy .env.example .env

# Linux/macOS
cp .env.example .env
```

If `.env.example` doesn't exist, create a `.env` file with the following content:

```env
# Django Core Settings
SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# Database Configuration (PostgreSQL with PostGIS)
DATABASE_NAME=civicview
DATABASE_USER=your_postgres_username
DATABASE_PASSWORD=your_postgres_password
DATABASE_HOST=localhost
DATABASE_PORT=5432

# Celery / Redis Configuration
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# CORS Configuration (optional extras)
# Local defaults already include localhost:3000 and localhost:5173 in settings.py
CORS_ALLOWED_ORIGINS_EXTRA=
```

**Important:** Replace the placeholder values:
- `SECRET_KEY`: Generate a secure key (you can use: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- `DATABASE_USER`: Your PostgreSQL username (default is often `postgres`)
- `DATABASE_PASSWORD`: Your PostgreSQL password

### Step 5: Configure GDAL/GEOS Paths (Windows Only)

**IMPORTANT for Windows users:** You must update the GDAL and GEOS library paths in `civicview_project/settings.py` to match your Conda environment location.

1. Find your Conda environment path:
   ```bash
   conda env list
   ```

2. Open `civicview_project/settings.py` and locate these lines (around lines 168-169):
   ```python
   GDAL_LIBRARY_PATH = r"C:\Users\patri\miniconda3\envs\civicview\Library\bin\gdal.dll"
   GEOS_LIBRARY_PATH = r"C:\Users\patri\miniconda3\envs\civicview\Library\bin\geos_c.dll"
   ```

3. Update the paths to match your Conda installation:
   - Replace `C:\Users\patri\miniconda3` with your Conda installation path
   - Replace `envs\civicview` with your environment name if different
   - Example paths:
     - Miniconda: `C:\Users\YourUsername\miniconda3\envs\civicview\Library\bin\gdal.dll`
     - Anaconda: `C:\Users\YourUsername\anaconda3\envs\civicview\Library\bin\gdal.dll`

4. Verify the files exist at those paths:
   - `gdal.dll` should be at: `[conda_path]\envs\civicview\Library\bin\gdal.dll`
   - `geos_c.dll` should be at: `[conda_path]\envs\civicview\Library\bin\geos_c.dll`

**Note:** Linux and macOS users typically don't need to configure these paths as they're usually found automatically.

### Step 6: Apply Database Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 7: Create Django Superuser

Create an admin user to access the Django admin panel and to assign Council/Admin roles:

```bash
conda activate civicview
cd path/to/CivicView
python manage.py createsuperuser
```

Follow the prompts to set a username, email, and password.

**If you're not sure whether you already have one:** Run `createsuperuser` again with a *new* username; if you prefer to reuse an existing user, go to **Django admin** → **Users** → open a user → set **Staff** and **Superuser** if needed, and ensure they have a **Profile** with role **Council** or **Admin** to use the analytics Dashboard.

### Step 8: Verify Setup

Run Django's system check:

```bash
python manage.py check
```

You should see: `System check identified no issues (0 silenced).`

If you see errors related to GDAL or GEOS on Windows, double-check the paths in Step 5.

**"Page not found" when opening the site or admin:**
- **Django admin** is at **http://127.0.0.1:8000/admin/** (not "postgre" or "localhost:5432"). Make sure the Django server is running (`python manage.py runserver`) and you use that URL in the browser.
- **PostgreSQL** is the database (port 5432); you don’t open it in the browser. Use **pgAdmin**, **psql**, or another DB client to connect to the database. If you meant the **Django admin** page, use http://127.0.0.1:8000/admin/ after running `runserver`.

### Step 9: Start Redis Server

Make sure Redis is running. In a separate terminal:

**Windows:**
```bash
redis-server
# Or if installed via Docker:
docker run -d -p 6379:6379 redis:7
```

**Linux/macOS:**
```bash
redis-server
# Or if installed as a service:
sudo systemctl start redis  # Linux
brew services start redis   # macOS
```

### Step 10: Start Celery Worker

In a new terminal (with the Conda environment activated):

```bash
conda activate civicview
celery -A civicview_project worker -l info
```

Keep this terminal open. You should see messages like:
```
celery@hostname ready.
```

### Step 11: Start Django Development Server

In another terminal (with the Conda environment activated):

```bash
conda activate civicview
python manage.py runserver
```

The server will start at `http://127.0.0.1:8000/`

You can now:
- Access the API at: `http://127.0.0.1:8000/api/`
- Access the Django admin at: `http://127.0.0.1:8000/admin/`

## Frontend Setup

The React frontend provides an interactive map interface for viewing and submitting civic reports.

### Step 1: Install Frontend Dependencies

Navigate to the frontend directory and install npm packages:

```bash
cd frontend
npm install
```

### Step 2: Start Frontend Development Server

```bash
npm run dev
```

The frontend will start at `http://localhost:5173` (or the next available Vite port).

**Important:** Make sure the Django backend is running on `http://127.0.0.1:8000/` before using the frontend.

### Frontend Features

- **Interactive Map**: Leaflet-based map showing report locations and hotspot clusters
- **Click-to-Set Coordinates**: Click anywhere on the map to automatically populate latitude/longitude in the report form (blue marker indicates selected location)
- **Report Submission Form**: Submit civic issues with title, description, category, and location
- **Visual Indicators**: 
  - Red markers show individual reports
  - Orange polygons show detected hotspot clusters
  - Blue marker shows the currently selected location for new reports

### Frontend Development

The frontend uses:
- **React 18** for UI components
- **Vite** for fast development and building
- **Leaflet** and **React-Leaflet** for interactive maps
- **Axios** for API communication

To build for production:
```bash
npm run build
```

## API Endpoints

Base URL: `http://127.0.0.1:8000/api/`

### Create a Report
`POST /reports/`

Request body:
```json
{
  "title": "Streetlight out",
  "description": "No lighting on corner",
  "category": "Lighting",
  "latitude": 53.3498,
  "longitude": -6.2603
}
```

Response:
```json
{
  "id": 1,
  "title": "Streetlight out",
  "description": "No lighting on corner",
  "category": "Lighting",
  "geom": {
    "type": "Point",
    "coordinates": [-6.2603, 53.3498]
  },
  "created_at": "2024-01-15T10:30:00Z"
}
```

### List Reports
`GET /reports/`

Returns a list of all reports, ordered by most recent first.

### List Hotspots
`GET /hotspots/`

Returns a list of all detected hotspot clusters as polygons.

### Additional high-use endpoints

- `GET /auth/me/`
- `GET /auth/assignable-users/`
- `GET /notifications/`
- `PATCH /notifications/{id}/read/`
- `GET /counties/?minimal=1`
- `GET /constituencies/?minimal=1`
- `GET /councils/?minimal=1`
- `GET /analytics/summary/`
- `GET /analytics/dashboard/`
- `GET /analytics/advanced/`
- `GET /analytics/county-comparison/?counties=...`
- `GET /analytics/constituency-comparison/?constituencies=...`
- `GET /analytics/council-comparison/?councils=...`
- `GET /analytics/geographic-reports/?type=county|constituency|council&name=...`

## Adding more data and hotspots

To get more reports on the map and more hotspot clusters:

1. **Seed sample reports** (clustered around Irish cities/towns):
   ```bash
   python manage.py seed_reports
   ```
   Optional: add more reports with `--clusters` and `--scattered`:
   ```bash
   python manage.py seed_reports --clusters 6 --cluster-size 40 --scattered 120
   ```
   To clear existing reports and reseed:
   ```bash
   python manage.py seed_reports --reset
   ```

2. **Generate hotspots** from those reports (so orange clusters appear on the map):
   ```bash
   python manage.py generate_hotspots
   ```
   With custom DBSCAN settings (e.g. larger clusters, fewer points per cluster):
   ```bash
   python manage.py generate_hotspots --eps=400 --min-samples=3 --days-back=30
   ```

3. **From the dashboard**: Log in as staff/manager/admin → open the **Clustering lab** tab, set days back / eps / min samples, click **Run clustering**. Then go back to the home page to see updated hotspots on the map.

4. **Submitting via the app**: Use the report form on the home page (logged in) to add real reports; creating a report triggers hotspot regeneration in the background if Celery is running.

## Importing Administrative Boundaries

Boundary analytics rely on imported GeoJSON boundary files (county, Dáil constituency, and local council).

```bash
python manage.py import_boundaries
```

Useful options:

```bash
# Re-import councils only (faster when iterating on council shapes)
python manage.py import_boundaries --only-councils

# Provide custom files
python manage.py import_boundaries \
  --counties "civicview/data/boundaries/counties_ireland_osi.geojson" \
  --constituencies "civicview/data/boundaries/dail_constituencies_2023.geojson" \
  --councils "civicview/data/boundaries/local_councils_ireland.geojson"
```

## Hotspot Generation

Hotspots are generated using DBSCAN clustering algorithm to identify areas with multiple reports.

### Generate Hotspots (Management Command)

The simplest way to generate hotspots:

```bash
python manage.py generate_hotspots
```

This command:
- Queries all existing reports from the database
- Applies DBSCAN clustering in meters
- Buffers and simplifies resulting polygons
- Merges nearby cluster borders for cleaner hotspot outlines
- Stores hotspots in the database

**Note:** This replaces all existing hotspots. Run this after adding new reports to update hotspot detection.

### Generate Hotspots via Celery

If you want to use Celery for async processing:

1. Make sure Celery worker is running (see Step 10 in Setup)
2. From Django shell or a view:
   ```python
   from civicview.tasks import generate_hotspots
   generate_hotspots.delay()
   ```

### DBSCAN Parameters

The clustering uses these default parameters (defined in `civicview/tasks.py`):
- **eps=250m** (`EPS_METERS=250`)
- **min_samples=5** (`MIN_SAMPLES=5`)
- **buffer=120m** (`BUFFER_METERS=120`)
- **simplify tolerance=15m** (`SIMPLIFY_TOLERANCE_METERS=15`)
- **near-border merge threshold=30% of buffer radius** (`MERGE_THRESHOLD_RATIO=0.30`)

To adjust these parameters, edit the `generate_hotspots` function in `civicview/tasks.py`.

### Viewing Hotspots

- **Django Admin**: Navigate to `http://127.0.0.1:8000/admin/civicview/hotspot/`
- **Frontend Map**: Hotspots appear as orange polygons on the interactive map
- **API**: Query `GET /api/hotspots/` for JSON data

## Docker Setup (Optional)

For containerized deployment, use Docker Compose to run all services:

### Prerequisites
- Docker and Docker Compose installed
- `.env` file configured (see Step 4 in Setup)

### Start All Services

```bash
docker compose up -d --build
```

This will start:
- **PostgreSQL with PostGIS** on port 5432
- **Redis** on port 6379
- **Django web server** on port 8000
- **Celery worker** for background tasks

### Initialize Database

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f web
docker compose logs -f worker
docker compose logs -f db
```

### Stop Services

```bash
docker compose down
```

**Note:** For local development with Conda, the Docker setup is optional. Use Docker if you prefer containerized development or for production deployment.

## Verification & Testing

### Automated test suite

- **Backend (Django + DRF + PostGIS/SpatiaLite):** from the project root with your Conda env active:
  ```bash
  python manage.py test civicview.tests
  ```
  `manage.py test` uses a local **SpatiaLite** file (`.test_spatialite.db`) so you do not need Postgres or `.env` for the default run. County/constituency API tests that rely on PostgreSQL `::geography` SQL are **skipped** unless you run against PostGIS (production settings).

- **Frontend (Vitest + jsdom):**
  ```bash
  cd frontend
  npm test
  ```

- **Offline evaluation report (JSON):** same env as normal Django (requires `.env` / database like `runserver`):
  ```bash
  python manage.py evaluate_system
  python manage.py evaluate_system --include-db-counts
  ```
  Produces synthetic DBSCAN metrics, a fixed coordinate-validation matrix, and optional live DB counts for documentation or CI artifacts.

### Verify Backend is Running

1. **Check Django server**: Visit `http://127.0.0.1:8000/admin/` - you should see the Django admin login page
2. **Check API**: Visit `http://127.0.0.1:8000/api/reports/` - you should see an empty list `[]` or existing reports
3. **Check Hotspots API**: Visit `http://127.0.0.1:8000/api/hotspots/` - you should see an empty list `[]` or existing hotspots

### Test Report Creation

Using curl:
```bash
curl -X POST http://127.0.0.1:8000/api/reports/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Report",
    "description": "This is a test",
    "category": "Testing",
    "latitude": 51.509865,
    "longitude": -0.118092
  }'
```

Using Django Admin:
1. Go to `http://127.0.0.1:8000/admin/`
2. Log in with your superuser credentials
3. Navigate to "Reports" → "Add Report"
4. Fill in the form and save

### Verify Hotspot Generation

1. Create at least 2-3 reports in close proximity (within ~1km)
2. Run: `python manage.py generate_hotspots`
3. Check hotspots:
   - Django Admin: `http://127.0.0.1:8000/admin/civicview/hotspot/`
   - API: `http://127.0.0.1:8000/api/hotspots/`
   - Frontend map: Should show orange polygons

### Verify Frontend

1. Ensure backend is running on `http://127.0.0.1:8000/`
2. Start frontend: `cd frontend && npm run dev`
3. Open browser to the frontend URL (typically `http://localhost:5173`)
4. You should see:
   - A map centered on Ireland by default
   - A report submission form
   - Existing reports as markers (if any)
   - Existing hotspots as polygons (if any)
5. Test map click: Click on the map - a blue marker should appear and coordinates should populate in the form

## Troubleshooting

### Common Issues

#### 1. GDAL/GEOS Library Not Found (Windows)

**Error:** `django.core.exceptions.ImproperlyConfigured: Could not find the GDAL library`

**Solution:**
- Update the `GDAL_LIBRARY_PATH` and `GEOS_LIBRARY_PATH` in `civicview_project/settings.py` (see Step 5 in Setup)
- Verify the files exist at those paths
- Make sure the Conda environment is activated

#### 2. Database Connection Error

**Error:** `django.db.utils.OperationalError: could not connect to server`

**Solutions:**
- Verify PostgreSQL is running: `psql -U postgres -c "SELECT version();"`
- Check database credentials in `.env` file
- Ensure PostGIS extension is installed: `psql -U postgres -d civicview -c "CREATE EXTENSION IF NOT EXISTS postgis;"`
- Verify database exists: `psql -U postgres -l` should list `civicview`

#### 3. Redis Connection Error

**Error:** `Error 111 connecting to localhost:6379`

**Solutions:**
- Start Redis server (see Step 9 in Setup)
- Check Redis is running: `redis-cli ping` should return `PONG`
- Verify Redis URL in `.env` file matches your Redis setup

#### 4. Celery Worker Not Processing Tasks

**Solutions:**
- Ensure Celery worker is running in a separate terminal
- Check Celery worker logs for errors
- Verify Redis is running and accessible
- Restart Celery worker after code changes

#### 5. Frontend Can't Connect to Backend

**Error:** CORS errors or network errors in browser console

**Solutions:**
- Ensure Django backend is running on `http://127.0.0.1:8000/`
- Check CORS settings in `.env` file include your frontend URL
- Verify `CORS_ALLOWED_ORIGINS` in settings.py includes the frontend origin
- Check browser console for specific error messages

#### 6. No Hotspots Appearing

**Solutions:**
- Ensure you have at least 2 reports close together (within ~1km)
- Run hotspot generation: `python manage.py generate_hotspots`
- Check hotspots exist: Visit `http://127.0.0.1:8000/api/hotspots/`
- Verify hotspot polygons have valid geometry in Django admin

#### 7. Conda Environment Issues

**Error:** Packages not found or import errors

**Solutions:**
- Ensure environment is activated: `conda activate civicview`
- Recreate environment (Conda): `conda env remove -n civicview && conda env create -f environment-local.yml`
- Update packages: `conda update --all`

### Getting Help

1. Check Django logs: Look at terminal output when running `python manage.py runserver`
2. Check Celery logs: Look at terminal output from Celery worker
3. Check browser console: F12 → Console tab for frontend errors
4. Verify all prerequisites are installed and running
5. Ensure `.env` file is configured correctly
6. Verify database migrations are applied: `python manage.py showmigrations`

## Project Structure

```
CivicView/
├── civicview/                  # Main Django app
│   ├── management/
│   │   └── commands/
│   │       ├── generate_hotspots.py  # CLI command for hotspot generation
│   │       └── import_boundaries.py  # GeoJSON boundary importer
│   ├── migrations/             # Database migrations
│   ├── models.py              # Reports, hotspots, boundaries, roles, notifications
│   ├── serializers.py         # DRF serializers
│   ├── tasks.py               # Celery tasks (DBSCAN clustering)
│   ├── views.py               # Report/hotspot/boundary API viewsets
│   ├── analytics_views.py     # Dashboard and advanced analytics endpoints
│   └── urls.py                # URL routing
├── civicview_project/         # Django project settings
│   ├── settings.py            # Main configuration (edit GDAL/GEOS paths here on Windows)
│   ├── urls.py                # Root URL configuration
│   └── celery.py              # Celery configuration
├── frontend/                  # React frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── MapView.jsx    # Leaflet map component
│   │   │   ├── ReportForm.jsx # Report submission form
│   │   │   ├── Dashboard.jsx  # Management dashboard
│   │   │   └── AdvancedAnalyticsWrapper.jsx
│   │   ├── App.jsx            # Main React component
│   │   └── api.js             # API client
│   └── package.json
├── .env                       # Environment variables (create from .env.example)
├── environment-local.yml      # Optional local Conda environment spec
├── requirements.txt           # Python dependencies
├── docker-compose.yml         # Docker Compose configuration
└── README.md                  # This file
```

## Quick Start Checklist

- [ ] Python environment created and dependencies installed (`pip install -r requirements.txt`)
- [ ] PostgreSQL with PostGIS installed and database created
- [ ] Redis server running
- [ ] `.env` file created and configured
- [ ] GDAL/GEOS paths updated in `settings.py` (Windows only)
- [ ] Database migrations applied
- [ ] Django superuser created
- [ ] Django server running (`python manage.py runserver`)
- [ ] Celery worker running (`celery -A civicview_project worker -l info`)
- [ ] Frontend dependencies installed (`cd frontend && npm install`)
- [ ] Frontend server running (`npm run dev`)
- [ ] Boundaries imported (`python manage.py import_boundaries`)
- [ ] Tested report creation
- [ ] Tested hotspot generation

## Next Steps

Once everything is running:
1. Create some test reports via the frontend or API
2. Generate hotspots: `python manage.py generate_hotspots`
3. Explore the Django admin interface
4. Customize DBSCAN parameters in `civicview/tasks.py` if needed
5. Adjust map center/zoom in `frontend/src/components/MapView.jsx` for your region

