#!/bin/bash

# Django Development Setup Script
# This script helps set up the development environment

echo "🚀 Django CI/CD Development Template Setup"
echo "=========================================="

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo "❌ Docker is not running. Please start Docker and try again."
        exit 1
    fi
    echo "✅ Docker is running"
}

# Function to check if docker-compose is available
check_docker_compose() {
    if ! command -v docker-compose &> /dev/null; then
        echo "❌ docker-compose not found. Please install docker-compose."
        exit 1
    fi
    echo "✅ docker-compose is available"
}

# Function to create .env.dev if it doesn't exist
create_env_file() {
    if [ ! -f .env.dev ]; then
        echo "📄 Creating .env.dev file..."
        cat > .env.dev << EOF
# Django settings
DJANGO_SECRET_KEY=your-secret-key-change-in-production
DEBUG=True

# Database settings
POSTGRES_DB=django_dev
POSTGRES_USER=postgres_user
POSTGRES_PASSWORD=postgres_password
DB_HOST=db
DB_PORT=5432

# Django allowed hosts
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,web,nginx

# Add your API keys here
GOOGLE_OAUTH2_CLIENT_ID=your-client-id
GOOGLE_OAUTH2_CLIENT_SECRET=your-client-secret
EOF
        echo "✅ .env.dev file created. Please update it with your actual values."
    else
        echo "✅ .env.dev file already exists"
    fi
}

# Main setup function
main() {
    echo ""
    echo "🔍 Checking prerequisites..."
    check_docker
    check_docker_compose
    
    echo ""
    echo "📁 Setting up environment..."
    create_env_file
    
    echo ""
    echo "🐳 Building and starting containers..."
    docker-compose -f docker-compose.dev.yml down
    docker-compose -f docker-compose.dev.yml up --build -d
    
    echo ""
    echo "⏳ Waiting for services to start..."
    sleep 10
    
    echo ""
    echo "🎉 Setup complete!"
    echo ""
    echo "📝 Next steps:"
    echo "1. Visit http://localhost to see your Django app"
    echo "2. Visit http://localhost:8000 to access Django directly"
    echo "3. Create a superuser: docker-compose -f docker-compose.dev.yml exec web python manage.py createsuperuser"
    echo ""
    echo "📊 View logs: docker-compose -f docker-compose.dev.yml logs -f"
    echo "🛑 Stop services: docker-compose -f docker-compose.dev.yml down"
    echo ""
    echo "📖 See DEVELOPMENT_SETUP_README.md for detailed documentation"
}

# Handle command line arguments
case "$1" in
    "start")
        echo "🚀 Starting development environment..."
        docker-compose -f docker-compose.dev.yml up -d
        echo "✅ Services started. Visit http://localhost"
        ;;
    "stop")
        echo "🛑 Stopping development environment..."
        docker-compose -f docker-compose.dev.yml down
        echo "✅ Services stopped"
        ;;
    "restart")
        echo "🔄 Restarting development environment..."
        docker-compose -f docker-compose.dev.yml down
        docker-compose -f docker-compose.dev.yml up -d
        echo "✅ Services restarted"
        ;;
    "logs")
        docker-compose -f docker-compose.dev.yml logs -f
        ;;
    "shell")
        docker-compose -f docker-compose.dev.yml exec web python manage.py shell
        ;;
    "superuser")
        docker-compose -f docker-compose.dev.yml exec web python manage.py createsuperuser
        ;;
    "migrate")
        docker-compose -f docker-compose.dev.yml exec web python manage.py makemigrations
        docker-compose -f docker-compose.dev.yml exec web python manage.py migrate
        ;;
    "collect-static")
        docker-compose -f docker-compose.dev.yml exec web python manage.py collectstatic --noinput
        ;;
    "flush")
        validate_env_file
        docker-compose -f docker-compose.dev.yml exec web python manage.py flush --noinput
        ;;
    "clean")
        echo "🧹 Cleaning up containers and volumes..."
        docker-compose -f docker-compose.dev.yml down -v
        docker system prune -f
        echo "✅ Cleanup complete"
        ;;
    *)
        if [ "$1" != "" ]; then
            echo "❌ Unknown command: $1"
            echo ""
        fi
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  (no args)     - Full setup (first time use)"
        echo "  start         - Start development environment"
        echo "  stop          - Stop development environment"
        echo "  restart       - Restart development environment"
        echo "  logs          - View service logs"
        echo "  shell         - Open Django shell"
        echo "  superuser     - Create Django superuser"
        echo "  migrate       - Run Django migrations"
        echo "  collect-static - Collect static files"
        echo "  clean         - Clean up containers and volumes"
        echo ""
        if [ "$1" == "" ]; then
            main
        fi
        ;;
esac