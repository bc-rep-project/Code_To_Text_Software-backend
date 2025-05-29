#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "🚀 Starting Render.com build process for Code2Text API..."

# Upgrade pip to latest version
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Verify gunicorn installation
echo "🔍 Verifying gunicorn installation..."
which gunicorn || echo "❌ Gunicorn not found!"
gunicorn --version || echo "❌ Gunicorn version check failed!"

# Collect static files for Django admin and other static assets
echo "🎨 Collecting static files..."
python manage.py collectstatic --noinput

# Check database connection before running migrations
echo "🔍 Testing Supabase database connection..."
python -c "
import os
import psycopg2
from urllib.parse import urlparse

try:
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        print('❌ DATABASE_URL environment variable not set!')
        exit(1)
    
    url = urlparse(db_url)
    print(f'Connecting to Supabase at {url.hostname}:{url.port}...')
    
    # Test connection
    conn = psycopg2.connect(db_url)
    conn.close()
    print('✅ Supabase database connection successful!')
    
except psycopg2.OperationalError as e:
    print(f'❌ Database connection failed: {e}')
    if 'Network is unreachable' in str(e):
        print('💡 Check your DATABASE_URL format and ensure it includes ?sslmode=require')
        print('💡 Expected format: postgresql://user:pass@aws-0-region.pooler.supabase.com:6543/postgres?sslmode=require')
    elif 'authentication failed' in str(e):
        print('💡 Check your database password in the DATABASE_URL')
    exit(1)
except Exception as e:
    print(f'❌ Unexpected error: {e}')
    exit(1)
"

# Apply database migrations
echo "🗄️ Applying database migrations..."
python manage.py migrate --noinput

# Create cache table if using database cache (optional)
echo "🗄️ Creating cache table..."
python manage.py createcachetable || echo "Cache table already exists or not needed"

echo "✅ Build process completed successfully!"
echo "📋 Installed packages:"
pip list | grep -E "(gunicorn|django|psycopg2)"