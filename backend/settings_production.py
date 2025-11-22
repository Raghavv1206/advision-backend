# backend/backend/settings_production.py
from .settings import *
import dj_database_url
import os

# ============================================================================
# PRODUCTION SECURITY
# ============================================================================
DEBUG = False

# Add your domains here - UPDATE THESE with your actual domains
ALLOWED_HOSTS = [
    'advision-backend.onrender.com',  # Replace with your actual Render URL
    '.onrender.com',                   # Allow all onrender.com subdomains
    'localhost',
    '127.0.0.1',
]

# Security settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Proxy settings for Render
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

# ============================================================================
# DATABASE - PostgreSQL on Render
# ============================================================================
DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# ============================================================================
# STATIC FILES (WhiteNoise)
# ============================================================================
# Insert WhiteNoise after SecurityMiddleware
if 'whitenoise.middleware.WhiteNoiseMiddleware' not in MIDDLEWARE:
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Create staticfiles directory if it doesn't exist
os.makedirs(STATIC_ROOT, exist_ok=True)

# ============================================================================
# CORS - Update with your Vercel frontend URL
# ============================================================================
# Get frontend URL from environment or use default
FRONTEND_URL = os.getenv('FRONTEND_URL', 'https://advision-frontend.vercel.app')

CORS_ALLOWED_ORIGINS = [
    FRONTEND_URL,
    "https://advision-frontend.vercel.app",  # Replace with your actual Vercel URL
    "https://advision.vercel.app",
]

# Remove duplicates
CORS_ALLOWED_ORIGINS = list(set(CORS_ALLOWED_ORIGINS))

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CSRF_TRUSTED_ORIGINS = [
    FRONTEND_URL,
    "https://advision-frontend.vercel.app",
    "https://advision.vercel.app",
    "https://advision-backend.onrender.com",  # Replace with your actual Render URL
]

# Remove duplicates
CSRF_TRUSTED_ORIGINS = list(set(CSRF_TRUSTED_ORIGINS))

# ============================================================================
# GOOGLE OAUTH SETTINGS
# ============================================================================
GOOGLE_OAUTH_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')

# ============================================================================
# API ENCRYPTION KEY - Use environment variable in production
# ============================================================================
API_ENCRYPTION_KEY = os.getenv('API_ENCRYPTION_KEY', SECRET_KEY)

# ============================================================================
# CLOUDINARY CONFIGURATION (Override for production if needed)
# ============================================================================
import cloudinary

cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

USE_CLOUDINARY = True

# ============================================================================
# AI API KEYS
# ============================================================================
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
STABILITY_API_KEY = os.getenv('STABILITY_API_KEY', '')

# ============================================================================
# LOGGING
# ============================================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'core': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# ============================================================================
# REPORT STORAGE PATH
# ============================================================================
REPORT_STORAGE_PATH = os.path.join(BASE_DIR, 'reports')
os.makedirs(REPORT_STORAGE_PATH, exist_ok=True)