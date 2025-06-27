#!/bin/bash

echo "Setting up production environment..."

if [ ! -f .env.prod ]; then
    cp env.prod.example .env.prod
    echo "Created .env.prod file"
fi

echo "Creating production database if it doesn't exist..."

docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d db

sleep 10

# Create database if it doesn't exist
docker-compose -f docker-compose.prod.yml exec -T db psql -U postgres_user postgres -c "SELECT 1 FROM pg_database WHERE datname='django_prod'" | grep -q 1 || docker-compose -f docker-compose.prod.yml exec -T db psql -U postgres_user postgres -c "CREATE DATABASE django_prod;"

docker-compose -f docker-compose.prod.yml run --rm web python manage.py makemigrations
docker-compose -f docker-compose.prod.yml run --rm web python manage.py migrate
docker-compose -f docker-compose.prod.yml run --rm web python manage.py collectstatic --noinput

# Start web and nginx services first
docker-compose -f docker-compose.prod.yml up -d web nginx

echo "Production setup complete!"
echo "Note: SSL certificate setup requires manual configuration or proper domain DNS setup."