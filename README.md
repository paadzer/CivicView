# Civic View

Civic View is a GeoDjango-powered civic issue reporting platform that exposes a REST API, runs DBSCAN-based hotspot clustering with Celery, and optionally visualises data through a lightweight React + Leaflet frontend. It matches the interim smart-city report goals: citizen reporting UI, automated DBSCAN hotspot detection, spatial storage in PostGIS, and map-based insight sharing.

## Architecture Overview

- **Presentation layer**: React + Leaflet (`frontend/`)
- **Application layer**: Django REST Framework (`civicview/`)
- **Data layer**: PostgreSQL + PostGIS
- **Processing layer**: Celery + Redis + DBSCAN (scikit-learn)

### Features

- **Authentication & roles**: Token auth; register/login; roles (citizen, moderator, admin) for permissions; only authenticated users can create reports; only owner or moderator/admin can update or delete.
- **Category filters**: Filter reports by category in the API (`?category=...`) and in the frontend dropdown.
- **Location validation**: Reports must be within Ireland (lat 51.4–55.4, lon -11 to -5); validated on backend and frontend.
- **Auto-refresh hotspots**: Creating a report triggers Celery task `generate_hotspots` so hotspots update automatically.
- **Map UI**: Layer toggles (show/hide reports and hotspots); category shown in report popups.

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

### Step 2: Create Conda Environment

```bash
conda env create -f environment.yml
conda activate civicview
```

This will install all required dependencies including:
- Django and Django REST Framework
- GeoDjango dependencies (GDAL, GEOS, PROJ)
- PostgreSQL client (psycopg2)
- Celery and Redis client
- Scikit-learn for DBSCAN clustering
- Shapely for geometric operations

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

# CORS Configuration (React Frontend)
CORS_ALLOWED_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
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

The frontend will start at `http://localhost:3000` (or the next available port).

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
  "latitude": 51.5,
  "longitude": -0.12
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
    "coordinates": [-0.12, 51.5]
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

## Hotspot Generation

Hotspots are generated using DBSCAN clustering algorithm to identify areas with multiple reports.

### Generate Hotspots (Management Command)

The simplest way to generate hotspots:

```bash
python manage.py generate_hotspots
```

This command:
- Queries all existing reports from the database
- Applies DBSCAN clustering (eps=0.01, min_samples=2)
- Creates convex hull polygons for each cluster
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
- **eps=0.01**: Maximum distance between points to be in the same cluster (approximately 1km)
- **min_samples=2**: Minimum number of reports required to form a cluster

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
3. Open browser to the frontend URL (typically `http://localhost:3000`)
4. You should see:
   - A map centered on coordinates (default: London)
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
- Recreate environment: `conda env remove -n civicview && conda env create -f environment.yml`
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
│   │       └── generate_hotspots.py  # CLI command for hotspot generation
│   ├── migrations/             # Database migrations
│   ├── models.py              # Report and Hotspot models
│   ├── serializers.py         # DRF serializers
│   ├── tasks.py               # Celery tasks (DBSCAN clustering)
│   ├── views.py               # API viewsets
│   └── urls.py                # URL routing
├── civicview_project/         # Django project settings
│   ├── settings.py            # Main configuration (edit GDAL/GEOS paths here on Windows)
│   ├── urls.py                # Root URL configuration
│   └── celery.py              # Celery configuration
├── frontend/                  # React frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── MapView.jsx    # Leaflet map component
│   │   │   └── ReportForm.jsx # Report submission form
│   │   ├── App.jsx            # Main React component
│   │   └── api.js             # API client
│   └── package.json
├── .env                       # Environment variables (create from .env.example)
├── environment.yml            # Conda environment specification
├── docker-compose.yml         # Docker Compose configuration
└── README.md                  # This file
```

## Quick Start Checklist

- [ ] Conda environment created and activated
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
- [ ] Tested report creation
- [ ] Tested hotspot generation

## Next Steps

Once everything is running:
1. Create some test reports via the frontend or API
2. Generate hotspots: `python manage.py generate_hotspots`
3. Explore the Django admin interface
4. Customize DBSCAN parameters in `civicview/tasks.py` if needed
5. Adjust map center/zoom in `frontend/src/components/MapView.jsx` for your region

