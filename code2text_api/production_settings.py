"""
Production settings for Code2Text API on Render.com
"""

from .settings import *
import dj_database_url
import os

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Production allowed hosts - Updated with correct URL and environment variable support
ALLOWED_HOSTS = [
    'code-to-text-software-backend.onrender.com',  # Correct Render.com URL
    'localhost',
    '127.0.0.1',
]

# Add support for RENDER_EXTERNAL_HOSTNAME environment variable
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# Debug logging for deployment troubleshooting (remove after fixing)
print(f"DEBUG setting is: {DEBUG}")
print(f"ALLOWED_HOSTS is currently: {ALLOWED_HOSTS}")
print(f"RENDER_EXTERNAL_HOSTNAME from env is: {RENDER_EXTERNAL_HOSTNAME}")

# Add your frontend domain to CORS allowed origins
CORS_ALLOWED_ORIGINS = [
    "https://code-to-text-software-frontend.vercel.app",  # Correct frontend URL
    "http://localhost:3000",  # For local development
]

# Ensure CORS credentials are allowed
CORS_ALLOW_CREDENTIALS = True

# Additional CORS headers for API requests
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

# Database configuration for production
# Render.com provides DATABASE_URL environment variable
if 'DATABASE_URL' in os.environ:
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ.get('DATABASE_URL'),
            conn_max_age=600,
            conn_health_checks=True,
        )
    }

# Redis configuration for Celery (if using Render's Redis)
if 'REDIS_URL' in os.environ:
    CELERY_BROKER_URL = os.environ.get('REDIS_URL')
    CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL')

# Security settings for production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_SECONDS = 31536000
SECURE_REDIRECT_EXEMPT = []

# Only enable HTTPS redirect if you have SSL configured
# SECURE_SSL_REDIRECT = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True

# Logging configuration for production
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
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
        'code2text_api': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Static files configuration (already configured with Whitenoise in main settings)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# File upload settings for production
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB 