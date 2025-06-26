#!/bin/bash

# Script to fix Django custom user model migration issues
# This script handles the common issue where custom user model migrations haven't been created properly

set -e  # Exit on any error

echo "🔧 Django Custom User Model Migration Fix Script"
echo "==============================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in a Django project
if [ ! -f "manage.py" ]; then
    print_error "This script must be run from the Django project root directory (where manage.py is located)"
    exit 1
fi

print_status "Checking Django project structure..."

# Check if core_users app exists
if [ ! -d "core_users" ]; then
    print_error "core_users app directory not found"
    exit 1
fi

# Check if CustomUser model exists
if [ ! -f "core_users/models.py" ]; then
    print_error "core_users/models.py not found"
    exit 1
fi

# Check if AUTH_USER_MODEL is set in settings
if ! grep -q "AUTH_USER_MODEL.*core_users.CustomUser" core/settings.py; then
    print_warning "AUTH_USER_MODEL might not be properly set in settings.py"
    print_status "Please ensure AUTH_USER_MODEL = 'core_users.CustomUser' is set in your settings.py"
fi

print_status "Step 1: Creating migration directories..."

# Create migrations directories if they don't exist
mkdir -p core_users/migrations
mkdir -p core_home/migrations

# Create __init__.py files
touch core_users/migrations/__init__.py
touch core_home/migrations/__init__.py

print_success "Migration directories created"

print_status "Step 2: Removing existing migration files (if any)..."

# Remove any existing migration files except __init__.py
find core_users/migrations -name "*.py" ! -name "__init__.py" -delete 2>/dev/null || true
find core_home/migrations -name "*.py" ! -name "__init__.py" -delete 2>/dev/null || true

print_success "Existing migration files removed"

print_status "Step 3: Checking database connection..."

# Function to run Django commands in Docker
run_django_cmd() {
    if [ -f "docker-compose.dev.yml" ]; then
        docker-compose -f docker-compose.dev.yml exec web python manage.py "$@"
    elif [ -f "docker-compose.yml" ]; then
        docker-compose exec web python manage.py "$@"
    else
        python manage.py "$@"
    fi
}

# Test database connection
if ! run_django_cmd check --database default; then
    print_error "Database connection failed. Please check your database settings and ensure Docker containers are running."
    exit 1
fi

print_success "Database connection verified"

print_status "Step 4: Dropping and recreating database (if using Docker)..."

# Check if using Docker
if [ -f "docker-compose.dev.yml" ] || [ -f "docker-compose.yml" ]; then
    print_warning "Docker detected. You may need to reset the database."
    read -p "Do you want to reset the Docker database? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [ -f "scripts/flush_docker_database.sh" ]; then
            print_status "Running database flush script..."
            bash scripts/flush_docker_database.sh
        else
            print_status "Stopping Docker containers..."
            docker-compose -f docker-compose.dev.yml down -v 2>/dev/null || docker-compose down -v 2>/dev/null || true
            
            print_status "Starting Docker containers..."
            docker-compose -f docker-compose.dev.yml up -d db 2>/dev/null || docker-compose up -d db 2>/dev/null || true
            
            # Wait for database to be ready
            print_status "Waiting for database to be ready..."
            sleep 10
        fi
    fi
fi

print_status "Step 5: Creating initial migrations for custom user model..."

# Create migrations for core_users first (this must be done before other apps)
run_django_cmd makemigrations core_users

print_success "Custom user migrations created"

print_status "Step 6: Creating migrations for other apps..."

# Create migrations for other apps
run_django_cmd makemigrations

print_success "All migrations created"

print_status "Step 7: Running migrations..."

# Run migrations
run_django_cmd migrate

print_success "All migrations applied successfully"

print_status "Step 8: Creating superuser (optional)..."

read -p "Do you want to create a superuser? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "scripts/create_superuser.sh" ]; then
        bash scripts/create_superuser.sh
    else
        run_django_cmd createsuperuser
    fi
fi

print_success "✅ Django custom user model migration fix completed successfully!"
echo
print_status "Summary of actions taken:"
echo "  - Created migration directories"
echo "  - Removed conflicting migration files"
echo "  - Created new migrations for custom user model"
echo "  - Applied all migrations"
echo "  - Optionally created superuser"
echo
print_status "Your Django project should now be working properly with the custom user model."
