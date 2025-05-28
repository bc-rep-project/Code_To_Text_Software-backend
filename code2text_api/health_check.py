"""
Health check views for monitoring application status
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
from django.core.cache import cache
import redis
from django.conf import settings
import os

@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """
    Basic health check endpoint
    """
    return JsonResponse({
        "status": "healthy",
        "service": "Code2Text API",
        "version": "1.0.0"
    })

@csrf_exempt
@require_http_methods(["GET"])
def health_check_detailed(request):
    """
    Detailed health check with database and Redis connectivity
    """
    health_status = {
        "status": "healthy",
        "service": "Code2Text API",
        "version": "1.0.0",
        "checks": {}
    }
    
    # Check database connectivity
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health_status["checks"]["database"] = "healthy"
    except Exception as e:
        health_status["checks"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check Redis connectivity (if configured)
    try:
        if hasattr(settings, 'CELERY_BROKER_URL') and settings.CELERY_BROKER_URL:
            # Try to connect to Redis
            import redis
            redis_url = settings.CELERY_BROKER_URL
            r = redis.from_url(redis_url)
            r.ping()
            health_status["checks"]["redis"] = "healthy"
        else:
            health_status["checks"]["redis"] = "not_configured"
    except Exception as e:
        health_status["checks"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check environment variables
    required_env_vars = [
        'DJANGO_SECRET_KEY',
        'DATABASE_URL',
    ]
    
    missing_vars = []
    for var in required_env_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        health_status["checks"]["environment"] = f"missing: {', '.join(missing_vars)}"
        health_status["status"] = "unhealthy"
    else:
        health_status["checks"]["environment"] = "healthy"
    
    status_code = 200 if health_status["status"] == "healthy" else 503
    return JsonResponse(health_status, status=status_code) 