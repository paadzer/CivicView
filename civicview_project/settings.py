# Import standard library modules
import os
from pathlib import Path
# Import django-environ for environment variable management
import environ

# Base directory: Points to the project root (parent of settings.py directory)
# Used for constructing absolute paths to project files
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
# Allows configuration via .env file instead of hardcoding sensitive values
env = environ.Env(DEBUG=(bool, False))
ENV_FILE = BASE_DIR / ".env"
# Only load .env file if it exists (optional for production)
if ENV_FILE.exists():
    environ.Env.read_env(ENV_FILE)

# ------------------------------------------------------------
# Core Django Settings
# ------------------------------------------------------------

# Secret key for cryptographic signing (must be unique and secret in production)
# Used for session security, CSRF protection, etc.
SECRET_KEY = env("SECRET_KEY", default="unsafe-secret-key")
# Debug mode: Shows detailed error pages in development (set False in production)
DEBUG = env.bool("DEBUG", default=True)

# List of host/domain names this Django site can serve
# Prevents HTTP Host header attacks
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])

# ------------------------------------------------------------
# Installed Apps
# ------------------------------------------------------------

# List of Django applications enabled for this project
INSTALLED_APPS = [
    # Django core apps
    "django.contrib.admin",  # Admin interface
    "django.contrib.auth",  # Authentication system
    "django.contrib.contenttypes",  # Content type framework
    "django.contrib.sessions",  # Session framework
    "django.contrib.messages",  # Messaging framework
    "django.contrib.staticfiles",  # Static file management

    # GeoDjango: Provides spatial database fields and geographic operations
    "django.contrib.gis",

    # Third-party apps
    "corsheaders",  # Handles Cross-Origin Resource Sharing (CORS) for React frontend
    "rest_framework",  # Django REST Framework for building REST APIs
    "rest_framework.authtoken",  # Token authentication for API
    "django_filters",  # Filtering for DRF (e.g. category filter on reports)

    # Your app: Main civic reporting application
    "civicview",
]

# ------------------------------------------------------------
# Middleware
# ------------------------------------------------------------

# Middleware classes: Process requests/responses in order (top to bottom)
# Each middleware can modify request/response or short-circuit processing
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # Must be first: Handles CORS headers for API
    "django.middleware.security.SecurityMiddleware",  # Security enhancements (HTTPS redirect, etc.)
    "django.contrib.sessions.middleware.SessionMiddleware",  # Manages sessions
    "django.middleware.common.CommonMiddleware",  # Common utilities (URL normalization, etc.)
    "django.middleware.csrf.CsrfViewMiddleware",  # CSRF protection for forms
    "django.contrib.auth.middleware.AuthenticationMiddleware",  # Associates users with requests
    "django.contrib.messages.middleware.MessageMiddleware",  # Handles temporary messages
    "django.middleware.clickjacking.XFrameOptionsMiddleware",  # Prevents clickjacking attacks
]

# Python path to the root URL configuration module
ROOT_URLCONF = "civicview_project.urls"

# ------------------------------------------------------------
# Templates
# ------------------------------------------------------------

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "civicview_project.wsgi.application"

# ------------------------------------------------------------
# Database (PostGIS)
# ------------------------------------------------------------

# Database configuration: Uses PostgreSQL with PostGIS extension
# PostGIS enables spatial data types (Point, Polygon) and geographic queries
DATABASES = {
    "default": {
        # PostGIS database backend (required for GeoDjango)
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        # Database name (must exist and have PostGIS extension enabled)
        "NAME": env("DATABASE_NAME"),
        # PostgreSQL username
        "USER": env("DATABASE_USER"),
        # PostgreSQL password
        "PASSWORD": env("DATABASE_PASSWORD"),
        # Database host (localhost for local development)
        "HOST": env("DATABASE_HOST", default="localhost"),
        # PostgreSQL port (default is 5432)
        "PORT": env("DATABASE_PORT", default="5432"),
    }
}

# ------------------------------------------------------------
# Password Validation
# ------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ------------------------------------------------------------
# Internationalisation
# ------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------
# Static Files
# ------------------------------------------------------------

STATIC_URL = "static/"

# Media files (user uploads, e.g. report images)
# Default to <project>/media locally, but allow overriding via MEDIA_ROOT env
MEDIA_ROOT = env("MEDIA_ROOT", default=str(BASE_DIR / "media"))
MEDIA_URL = "media/"

# ------------------------------------------------------------
# REST Framework
# ------------------------------------------------------------

# Django REST Framework configuration
REST_FRAMEWORK = {
    # Response renderers: JSON for API clients, Browsable for browser testing
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",  # JSON output for API
        "rest_framework.renderers.BrowsableAPIRenderer",  # HTML interface for testing
    ],
    # Authentication: Token auth for API (login returns token, client sends Authorization: Token <key>)
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Permissions: Read-only for anonymous; write requires authentication (overridden per-view)
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    # Filtering: Enable django-filter for queryset filtering (e.g. ?category=Lighting)
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    # Basic throttling to prevent spamming report submissions and other writes
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        # Adjust as needed; this caps how many requests a user/IP can make
        "user": "20/minute",
        "anon": "5/minute",
    },
}

# ------------------------------------------------------------
# CORS (React Frontend)
# ------------------------------------------------------------

# CORS configuration: Allows React frontend to make API requests
# Without this, browsers block cross-origin requests from React (port 3000) to Django (port 8000)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://civic-view.vercel.app",
]

# Trusted origins for CSRF-protected requests (e.g. admin login in production)
CSRF_TRUSTED_ORIGINS = [
    "https://civicview-production.up.railway.app",
    "https://civic-view.vercel.app",
]

# ------------------------------------------------------------
# Celery / Redis
# ------------------------------------------------------------

# Celery configuration: Enables asynchronous task processing
# Celery uses Redis as a message broker and result backend

# Redis URL for message broker: Where Celery sends tasks to be processed
CELERY_BROKER_URL = env(
    "CELERY_BROKER_URL",
    default=env("REDIS_URL", default="redis://localhost:6379/0"),
)

# Redis URL for result backend: Where Celery stores task results
CELERY_RESULT_BACKEND = env(
    "CELERY_RESULT_BACKEND",
    default=CELERY_BROKER_URL,  # Use same Redis instance for results
)

# ------------------------------------------------------------
# GeoDjango: GDAL + GEOS (Windows-only configuration)
# ------------------------------------------------------------

# On Windows development, these paths point to the Conda environment DLLs.
# On Linux (e.g. Railway), Django will rely on system libraries instead.
if os.name == "nt":
    GDAL_LIBRARY_PATH = r"C:\Users\patri\miniconda3\envs\civicview\Library\bin\gdal.dll"
    GEOS_LIBRARY_PATH = r"C:\Users\patri\miniconda3\envs\civicview\Library\bin\geos_c.dll"

# ------------------------------------------------------------
# Default primary key
# ------------------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
