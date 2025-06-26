#!/bin/bash

# Django Production Setup Script
# This script helps set up the production environment

echo "🚀 Django CI/CD Production Template Setup"
echo "=========================================="

# Function to check Docker availability and environment
check_production_environment() {
    echo "🔍 Checking production environment prerequisites..."
    
    # Check Docker
    if ! docker info > /dev/null 2>&1; then
        echo "❌ Docker is not running. Please start Docker and try again."
        exit 1
    fi
    echo "✅ Docker is running"
    
    # Check docker-compose
    if ! command -v docker-compose &> /dev/null; then
        echo "❌ docker-compose not found. Please install docker-compose."
        exit 1
    fi
    echo "✅ docker-compose is available"
    
    # Check if we're in the right directory
    if [ ! -f "docker-compose.prod.yml" ]; then
        echo "❌ docker-compose.prod.yml not found. Please run this script from the project root directory."
        exit 1
    fi
    echo "✅ Production Docker Compose file found"
    
    # Validate environment file
    validate_env_file
    echo "✅ Environment file validated"
}

# Function to create .env.prod if it doesn't exist
create_env_file() {
    if [ ! -f .env.prod ]; then
        echo "📄 Creating .env.prod file..."
        cat > .env.prod << EOF
# Django settings
DJANGO_SECRET_KEY=your-secret-key-change-in-production
DEBUG=False

# Database settings
POSTGRES_DB=django_prod
POSTGRES_USER=postgres_user
POSTGRES_PASSWORD=postgres_password
DB_HOST=db
DB_PORT=5432

# Django allowed hosts
ALLOWED_HOSTS=your-production-domain.com,localhost,127.0.0.1,web,nginx

# Add your API keys here
GOOGLE_OAUTH2_CLIENT_ID=your-client-id
GOOGLE_OAUTH2_CLIENT_SECRET=your-client-secret
EOF
        echo "✅ .env.prod file created. Please update it with your actual values."
        echo "⚠️  IMPORTANT: Update DJANGO_SECRET_KEY, database credentials, and ALLOWED_HOSTS before running in production!"
    else
        echo "✅ .env.prod file already exists"
    fi
}

# Function to validate .env.prod file
validate_env_file() {
    if [ ! -f .env.prod ]; then
        echo "❌ .env.prod file is missing!"
        echo "Creating a default .env.prod file..."
        create_env_file
        echo "⚠️  Please update the .env.prod file with your actual production values before continuing."
        read -p "Press Enter after updating .env.prod file, or Ctrl+C to exit..."
    fi
    
    # Check for placeholder values
    if grep -q "your-secret-key-change-in-production" .env.prod 2>/dev/null; then
        echo "⚠️  WARNING: .env.prod still contains placeholder values!"
        echo "Please update DJANGO_SECRET_KEY in .env.prod before running in production."
    fi
    
    if grep -q "your-production-domain.com" .env.prod 2>/dev/null; then
        echo "⚠️  WARNING: Please update ALLOWED_HOSTS in .env.prod with your actual domain."
    fi
}

# Main setup function
main() {
    echo ""
    check_production_environment

    echo ""
    echo "📁 Setting up production environment..."
    create_env_file

    echo ""
    echo "🐳 Building and starting production containers..."
    docker-compose -f docker-compose.prod.yml down
    docker-compose -f docker-compose.prod.yml up --build -d

    echo ""
    echo "⏳ Waiting for services to start..."
    sleep 15

    echo ""
    echo "🔍 Checking container health..."
    if docker-compose -f docker-compose.prod.yml ps | grep -q "Up"; then
        echo "✅ Production containers are running"
    else
        echo "❌ Some containers failed to start. Check logs with: docker-compose -f docker-compose.prod.yml logs"
        exit 1
    fi

    echo ""
    echo "🎉 Production setup complete!"
    echo ""
    echo "📝 Next steps:"
    echo "1. Visit http://localhost to see your Django app via Nginx"
    echo "2. Visit http://localhost:8000 to access Django directly"
    echo "3. Create a superuser: ./scripts/prod_setup.sh superuser"
    echo ""
    echo "📊 View logs: ./scripts/prod_setup.sh logs"
    echo "🛑 Stop services: ./scripts/prod_setup.sh stop"
    echo ""
    echo "⚠️  Production Security Checklist:"
    echo "  - Ensure DEBUG=False in .env.prod"
    echo "  - Use a strong SECRET_KEY"
    echo "  - Configure proper ALLOWED_HOSTS"
    echo "  - Review database credentials"
    echo "  - Configure SSL/HTTPS for production domain"
}

# Handle command line arguments
case "$1" in
    "start")
        validate_env_file
        echo "🚀 Starting production environment..."
        docker-compose -f docker-compose.prod.yml up -d
        echo "✅ Services started. Visit http://localhost"
        ;;
    "stop")
        echo "🛑 Stopping production environment..."
        docker-compose -f docker-compose.prod.yml down
        echo "✅ Services stopped"
        ;;
    "restart")
        validate_env_file
        echo "🔄 Restarting production environment..."
        docker-compose -f docker-compose.prod.yml down
        docker-compose -f docker-compose.prod.yml up -d
        echo "✅ Services restarted"
        ;;
    "logs")
        docker-compose -f docker-compose.prod.yml logs -f
        ;;
    "shell")
        validate_env_file
        docker-compose -f docker-compose.prod.yml exec web python manage.py shell
        ;;
    "superuser")
        validate_env_file
        echo "👤 Creating production superuser..."
        docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
        ;;
    "migrate")
        validate_env_file
        echo "🔄 Running production migrations..."
        echo "⚠️  For comprehensive migrations, consider using: ./scripts/make_migrations_prod.sh"
        docker-compose -f docker-compose.prod.yml exec web python manage.py makemigrations
        docker-compose -f docker-compose.prod.yml exec web python manage.py migrate
        ;;
    "collect-static")
        validate_env_file
        docker-compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
        ;;
    "flush")
        validate_env_file
        docker-compose -f docker-compose.prod.yml exec web python manage.py flush --noinput
        ;;
    "clean")
        echo "🧹 Cleaning up production containers and volumes..."
        echo "⚠️  This will remove all production data including the database!"
        read -p "Are you sure? Type 'YES' to confirm: " -r
        if [[ $REPLY == "YES" ]]; then
            docker-compose -f docker-compose.prod.yml down -v
            docker system prune -f
            echo "✅ Production cleanup complete"
        else
            echo "❌ Cleanup cancelled"
        fi
        ;;
    *)
        if [ "$1" != "" ]; then
            echo "❌ Unknown command: $1"
            echo ""
        fi
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  (no args)     - Full production setup (first time use)"
        echo "  start         - Start production environment"
        echo "  stop          - Stop production environment"
        echo "  restart       - Restart production environment"
        echo "  logs          - View service logs"
        echo "  shell         - Open Django shell"
        echo "  superuser     - Create Django superuser"
        echo "  migrate       - Run Django migrations (use make_migrations_prod.sh for comprehensive migration)"
        echo "  collect-static - Collect static files"
        echo "  clean         - Clean up containers and volumes (DESTRUCTIVE)"
        echo ""
        echo "📝 Production-specific scripts:"
        echo "  ./scripts/make_migrations_prod.sh  - Comprehensive migration management"
        echo "  ./scripts/core_user_customuser_migration_fix.sh  - Fix CustomUser issues"
        echo ""
        if [ "$1" == "" ]; then
            main
        fi
        ;;
esac