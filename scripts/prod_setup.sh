#!/bin/bash

echo "Setting up production environment..."

if [ ! -f .env.prod ]; then
    cp env.prod.example .env.prod
    echo "Created .env.prod file"
fi

docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d db

sleep 10

docker-compose -f docker-compose.prod.yml run --rm web python manage.py makemigrations
docker-compose -f docker-compose.prod.yml run --rm web python manage.py migrate
docker-compose -f docker-compose.prod.yml run --rm web python manage.py collectstatic --noinput

docker-compose -f docker-compose.prod.yml up -d

echo "Production setup complete!"