#!/bin/bash

echo "Setting up development environment..."

if [ ! -f .env.dev ]; then
    cp env.dev.example .env.dev
    echo "Created .env.dev file"
fi

docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.dev.yml build
docker-compose -f docker-compose.dev.yml up -d db

sleep 10

docker-compose -f docker-compose.dev.yml run --rm web python manage.py makemigrations
docker-compose -f docker-compose.dev.yml run --rm web python manage.py migrate

docker-compose -f docker-compose.dev.yml up

echo "Development setup complete!"