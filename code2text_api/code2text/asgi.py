"""
ASGI config for code2text project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'code2text.settings')

application = get_asgi_application() 