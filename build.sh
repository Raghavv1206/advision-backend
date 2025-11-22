#!/usr/bin/env bash
# exit on error
set -o errexit

# Print Python version for debugging
echo "Python version:"
python --version

# Upgrade pip first to avoid compatibility issues
pip install --upgrade pip

# Install production requirements
pip install -r requirements_prod.txt

# Collect static files for WhiteNoise
python manage.py collectstatic --no-input

# Run database migrations
python manage.py migrate

echo "Build completed successfully!"