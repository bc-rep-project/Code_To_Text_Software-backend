"""
WSGI config for code2text project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'code2text.settings')

application = get_wsgi_application() 