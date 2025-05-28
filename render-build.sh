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

# Apply database migrations
echo "🗄️ Applying database migrations..."
python manage.py migrate

# Create cache table if using database cache (optional)
echo "🗄️ Creating cache table..."
python manage.py createcachetable || echo "Cache table already exists or not needed"

echo "✅ Build process completed successfully!"
echo "📋 Installed packages:"
pip list | grep -E "(gunicorn|django)" 