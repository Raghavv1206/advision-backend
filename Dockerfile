# backend/Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files (if you serve them)
# RUN python manage.py collectstatic --noinput

# Gunicorn will be the entrypoint
CMD ["gunicorn", "backend.wsgi:application", "--bind", "0.0.0.0:8000"]