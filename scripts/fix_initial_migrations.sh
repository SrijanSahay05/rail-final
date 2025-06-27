#!/bin/bash

# Django Initial Migration Fix Script
# This script removes existing migrations and creates fresh ones in the correct order

set -e  # Exit on any error

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

# Function to check if we're in a Django project
check_django_project() {
    if [ ! -f "manage.py" ]; then
        print_error "This script must be run from the Django project root directory (where manage.py is located)"
        exit 1
    fi
    print_success "Django project detected"
}

# Function to check Docker environment
check_docker_environment() {
    if [ ! -f "docker-compose.dev.yml" ] && [ ! -f "docker-compose.prod.yml" ]; then
        print_error "No Docker Compose files found. Please run this script from the project root."
        exit 1
    fi
    
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_success "Docker environment ready"
}

# Function to determine which environment to use
get_environment() {
    if [ -f "docker-compose.dev.yml" ]; then
        echo "dev"
    elif [ -f "docker-compose.prod.yml" ]; then
        echo "prod"
    else
        echo "none"
    fi
}

# Function to run Django commands in the appropriate environment
run_django_cmd() {
    local env=$(get_environment)
    if [ "$env" = "dev" ]; then
        docker-compose -f docker-compose.dev.yml exec web python manage.py "$@"
    elif [ "$env" = "prod" ]; then
        docker-compose -f docker-compose.prod.yml exec web python manage.py "$@"
    else
        python manage.py "$@"
    fi
}

# Function to stop containers
stop_containers() {
    local env=$(get_environment)
    if [ "$env" = "dev" ]; then
        print_status "Stopping development containers..."
        docker-compose -f docker-compose.dev.yml down
    elif [ "$env" = "prod" ]; then
        print_status "Stopping production containers..."
        docker-compose -f docker-compose.prod.yml down
    fi
}

# Function to start database only
start_database() {
    local env=$(get_environment)
    if [ "$env" = "dev" ]; then
        print_status "Starting development database..."
        docker-compose -f docker-compose.dev.yml up -d db
    elif [ "$env" = "prod" ]; then
        print_status "Starting production database..."
        docker-compose -f docker-compose.prod.yml up -d db
    fi
}

# Function to start web service
start_web_service() {
    local env=$(get_environment)
    if [ "$env" = "dev" ]; then
        print_status "Starting development web service..."
        docker-compose -f docker-compose.dev.yml up -d web
    elif [ "$env" = "prod" ]; then
        print_status "Starting production web service..."
        docker-compose -f docker-compose.prod.yml up -d web
    fi
}

# Function to wait for database
wait_for_database() {
    print_status "Waiting for database to be ready..."
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if run_django_cmd check --database default > /dev/null 2>&1; then
            print_success "Database is ready"
            return 0
        fi
        print_status "Waiting for database... (attempt $attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done
    
    print_error "Database failed to become ready within expected time"
    return 1
}

# Function to remove existing migrations
remove_existing_migrations() {
    print_status "Removing existing migration files..."
    
    # Find and remove all migration files except __init__.py
    find . -path "*/migrations/*.py" ! -name "__init__.py" -delete 2>/dev/null || true
    find . -path "*/migrations/*.pyc" -delete 2>/dev/null || true
    
    print_success "Existing migration files removed"
}

# Function to create migration directories
create_migration_directories() {
    print_status "Creating migration directories..."
    
    # Create migrations directories for all apps
    mkdir -p core_users/migrations
    mkdir -p core_home/migrations
    mkdir -p feature_railways/migrations
    mkdir -p feature_transaction/migrations
    
    # Create __init__.py files
    touch core_users/migrations/__init__.py
    touch core_home/migrations/__init__.py
    touch feature_railways/migrations/__init__.py
    touch feature_transaction/migrations/__init__.py
    
    print_success "Migration directories created"
}

# Function to create migrations in correct order
create_migrations_in_order() {
    print_status "Creating migrations in correct order..."
    
    # Step 1: Create migrations for core_users first (since it's the AUTH_USER_MODEL)
    print_status "Creating migrations for core_users..."
    run_django_cmd makemigrations core_users
    
    # Step 2: Create migrations for all other apps
    print_status "Creating migrations for all other apps..."
    run_django_cmd makemigrations
    
    print_success "All migrations created"
}

# Function to apply migrations in correct order
apply_migrations_in_order() {
    print_status "Applying migrations in correct order..."
    
    # Step 1: Apply core_users migrations first
    print_status "Applying core_users migrations..."
    run_django_cmd migrate core_users
    
    # Step 2: Apply all remaining migrations
    print_status "Applying all remaining migrations..."
    run_django_cmd migrate
    
    print_success "All migrations applied successfully"
}

# Function to collect static files
collect_static_files() {
    print_status "Collecting static files..."
    run_django_cmd collectstatic --noinput
    print_success "Static files collected"
}

# Main function
main() {
    echo "🔧 Django Initial Migration Fix Script"
    echo "======================================"
    
    # Check prerequisites
    check_django_project
    check_docker_environment
    
    local env=$(get_environment)
    print_status "Using $env environment"
    
    # Stop all containers
    stop_containers
    
    # Remove existing migrations
    remove_existing_migrations
    
    # Create migration directories
    create_migration_directories
    
    # Start database
    start_database
    
    # Wait for database
    wait_for_database
    
    # Start web service
    start_web_service
    
    # Wait a bit for web service to be ready
    print_status "Waiting for web service to be ready..."
    sleep 10
    
    # Create migrations in correct order
    create_migrations_in_order
    
    # Apply migrations in correct order
    apply_migrations_in_order
    
    # Collect static files
    collect_static_files
    
    echo ""
    print_success "🎉 Initial migration fix completed successfully!"
    echo ""
    print_status "Summary of actions taken:"
    echo "  - Removed all existing migration files"
    echo "  - Created fresh migration directories"
    echo "  - Created migrations for core_users first"
    echo "  - Created migrations for all other apps"
    echo "  - Applied core_users migrations first"
    echo "  - Applied all remaining migrations"
    echo "  - Collected static files"
    echo ""
    print_status "Your Django project should now have clean, properly ordered migrations."
}

# Handle command line arguments
case "$1" in
    "help"|"-h"|"--help")
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  (no args) - Run full migration fix process"
        echo "  help      - Show this help message"
        echo ""
        echo "This script will:"
        echo "  1. Remove all existing migration files"
        echo "  2. Create fresh migration directories"
        echo "  3. Create migrations for core_users first"
        echo "  4. Create migrations for all other apps"
        echo "  5. Apply core_users migrations first"
        echo "  6. Apply all remaining migrations"
        echo "  7. Collect static files"
        echo ""
        ;;
    *)
        if [ "$1" != "" ]; then
            print_error "Unknown command: $1"
            echo "Use '$0 help' for usage information."
            exit 1
        fi
        main
        ;;
esac 