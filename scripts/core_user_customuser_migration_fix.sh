#!/bin/bash

# Script to fix Django "relation core_users_customuser does not exist" error
# This script specifically handles database table creation issues for CustomUser model

set -e  # Exit on any error

echo "🔧 Django CustomUser Relation Fix Script"
echo "========================================"

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

# Function to check Docker availability
check_docker_availability() {
    if [ -f "docker-compose.dev.yml" ] || [ -f "docker-compose.yml" ]; then
        if ! command -v docker >/dev/null 2>&1; then
            print_error "Docker is not installed or not in PATH"
            print_status "Please install Docker and try again, or run the script in a local Python environment"
            exit 1
        fi
        
        if ! command -v docker-compose >/dev/null 2>&1; then
            print_error "docker-compose is not installed or not in PATH"
            print_status "Please install docker-compose and try again"
            exit 1
        fi
        
        if ! docker info >/dev/null 2>&1; then
            print_error "Docker daemon is not running"
            print_status "Please start Docker and try again"
            exit 1
        fi
        
        print_success "Docker environment is available"
    else
        print_status "No Docker configuration found, will run in local Python environment"
    fi
}

# Check if we're in a Django project
if [ ! -f "manage.py" ]; then
    print_error "This script must be run from the Django project root directory (where manage.py is located)"
    exit 1
fi

print_status "Starting CustomUser relation fix process..."

# Check Docker availability first
check_docker_availability

# Function to run Django commands in Docker or locally
run_django_cmd() {
    local max_retries=3
    local retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        if [ -f "docker-compose.dev.yml" ]; then
            print_status "Running command in Docker dev environment..."
            if docker-compose -f docker-compose.dev.yml exec web python manage.py "$@"; then
                return 0
            else
                print_warning "Command failed, checking container status..."
                
                # Check if container is still running
                if ! docker-compose -f docker-compose.dev.yml ps --filter "status=running" | grep -q web; then
                    print_warning "Web container is not running, attempting to restart..."
                    docker-compose -f docker-compose.dev.yml up -d web
                    sleep 10
                fi
                
                retry_count=$((retry_count + 1))
                if [ $retry_count -lt $max_retries ]; then
                    print_status "Retrying command... (attempt $((retry_count + 1))/$max_retries)"
                    sleep 5
                fi
            fi
        elif [ -f "docker-compose.yml" ]; then
            print_status "Running command in Docker environment..."
            if docker-compose exec web python manage.py "$@"; then
                return 0
            else
                retry_count=$((retry_count + 1))
                if [ $retry_count -lt $max_retries ]; then
                    print_status "Retrying command... (attempt $((retry_count + 1))/$max_retries)"
                    sleep 5
                fi
            fi
        else
            print_status "Running command locally..."
            if python manage.py "$@"; then
                return 0
            else
                retry_count=$((retry_count + 1))
                if [ $retry_count -lt $max_retries ]; then
                    print_status "Retrying command... (attempt $((retry_count + 1))/$max_retries)"
                    sleep 5
                fi
            fi
        fi
    done
    
    print_error "Command failed after $max_retries attempts"
    return 1
}

# Function to check if Docker containers are running and start them if needed
check_docker_containers() {
    if [ -f "docker-compose.dev.yml" ]; then
        print_status "Checking Docker container status..."
        
        # Check if containers exist and are running
        if docker-compose -f docker-compose.dev.yml ps --services --filter "status=running" | grep -q web; then
            print_success "Docker containers are already running"
            return 0
        fi
        
        # Check if containers exist but are stopped
        if docker-compose -f docker-compose.dev.yml ps --services | grep -q web; then
            print_warning "Docker containers exist but are not running"
        else
            print_warning "Docker containers don't exist yet"
        fi
        
        print_status "Starting Docker containers automatically..."
        
        # Start containers (this will build if they don't exist)
        if docker-compose -f docker-compose.dev.yml up -d; then
            print_status "Waiting for containers to be ready..."
            
            # Wait for the web container to be healthy
            local max_wait=60
            local wait_time=0
            
            while [ $wait_time -lt $max_wait ]; do
                if docker-compose -f docker-compose.dev.yml ps --filter "status=running" | grep -q web; then
                    print_success "Web container is running"
                    break
                fi
                sleep 2
                wait_time=$((wait_time + 2))
                print_status "Waiting for web container... ($wait_time/$max_wait seconds)"
            done
            
            # Additional wait for database to be ready
            print_status "Waiting for database to be ready..."
            sleep 15
            
            # Verify database connection
            if run_django_cmd check --database default > /dev/null 2>&1; then
                print_success "Database connection verified"
            else
                print_warning "Database connection check failed, but continuing..."
            fi
        else
            print_error "Failed to start Docker containers"
            exit 1
        fi
    elif [ -f "docker-compose.yml" ]; then
        print_status "Checking Docker container status (production config)..."
        
        if docker-compose ps --services --filter "status=running" | grep -q web; then
            print_success "Docker containers are already running"
            return 0
        fi
        
        print_status "Starting Docker containers..."
        if docker-compose up -d; then
            print_status "Waiting for containers to be ready..."
            sleep 20
        else
            print_error "Failed to start Docker containers"
            exit 1
        fi
    else
        print_status "No Docker Compose configuration found, assuming local development"
    fi
}

print_status "Step 1: Checking Docker environment and containers..."
check_docker_containers
print_success "Environment check completed"

print_status "Step 2: Ensuring containers are healthy..."

# Additional health check for database connectivity
if [ -f "docker-compose.dev.yml" ] || [ -f "docker-compose.yml" ]; then
    print_status "Performing database connectivity test..."
    
    local db_ready=false
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ] && [ "$db_ready" = false ]; do
        if run_django_cmd check --database default > /dev/null 2>&1; then
            db_ready=true
            print_success "Database is ready and accessible"
        else
            print_status "Database not ready yet, waiting... (attempt $attempt/$max_attempts)"
            sleep 2
            attempt=$((attempt + 1))
        fi
    done
    
    if [ "$db_ready" = false ]; then
        print_error "Database is not accessible after waiting. Please check your database configuration."
        print_status "You can try running: docker-compose -f docker-compose.dev.yml logs db"
        exit 1
    fi
fi

print_status "Step 3: Checking current migration status..."

# Check if core_users migrations exist
if [ ! -d "core_users/migrations" ]; then
    print_status "Creating core_users migrations directory..."
    mkdir -p core_users/migrations
    touch core_users/migrations/__init__.py
fi

# Show current migration status
print_status "Current migration status:"
run_django_cmd showmigrations core_users || true

print_status "Step 4: Backing up existing migration files..."

# Create backup directory with timestamp
BACKUP_DIR="migration_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup existing migrations if they exist
if [ -d "core_users/migrations" ] && [ "$(ls -A core_users/migrations/*.py 2>/dev/null | grep -v __init__ || true)" ]; then
    print_status "Backing up existing core_users migrations..."
    cp core_users/migrations/*.py "$BACKUP_DIR/" 2>/dev/null || true
fi

print_success "Backup created in $BACKUP_DIR"

print_status "Step 5: Removing problematic migration files..."

# Remove existing migration files except __init__.py
find core_users/migrations -name "*.py" ! -name "__init__.py" -delete 2>/dev/null || true

print_success "Old migration files removed"

print_status "Step 6: Fake unapplying migrations to reset state..."

# Try to fake unapply migrations if they exist in database
run_django_cmd migrate core_users zero --fake || {
    print_warning "Could not fake unapply migrations (this is often expected)"
}

print_status "Step 7: Creating fresh CustomUser migrations..."

# Create new migration for CustomUser model
run_django_cmd makemigrations core_users --name "create_customuser_model"

print_success "New CustomUser migration created"

print_status "Step 8: Applying CustomUser migrations..."

# Apply the new migration
run_django_cmd migrate core_users

print_success "CustomUser migration applied successfully"

print_status "Step 9: Creating and applying other app migrations..."

# Create migrations for other apps that might depend on CustomUser
print_status "Creating migrations for all apps..."
run_django_cmd makemigrations

print_status "Applying all remaining migrations..."
run_django_cmd migrate

print_success "All migrations applied successfully"

print_status "Step 10: Verifying database table creation..."

# Verify that the CustomUser table exists
if run_django_cmd shell -c "
from django.db import connection
cursor = connection.cursor()
cursor.execute(\"SELECT count(*) FROM information_schema.tables WHERE table_name = 'core_users_customuser';\")
result = cursor.fetchone()[0]
print(f'CustomUser table exists: {result > 0}')
exit(0 if result > 0 else 1)
"; then
    print_success "✅ CustomUser table verified in database"
else
    print_error "❌ CustomUser table still not found in database"
    print_status "Attempting alternative verification..."
    
    # Alternative verification using Django ORM
    if run_django_cmd shell -c "
from core_users.models import CustomUser
try:
    count = CustomUser.objects.count()
    print(f'CustomUser model working, current count: {count}')
except Exception as e:
    print(f'Error: {e}')
    exit(1)
"; then
        print_success "✅ CustomUser model is working correctly"
    else
        print_error "❌ CustomUser model still has issues"
        exit 1
    fi
fi

print_status "Step 11: Testing user creation..."

# Test if we can create a user programmatically
if run_django_cmd shell -c "
from core_users.models import CustomUser
import uuid
test_username = f'test_user_{uuid.uuid4().hex[:8]}'
try:
    user = CustomUser.objects.create_user(
        username=test_username,
        email=f'{test_username}@example.com',
        password='testpass123',
        user_type='PASSENGER'
    )
    print(f'✅ Test user created successfully: {user.username}')
    # Clean up test user
    user.delete()
    print('✅ Test user cleaned up')
except Exception as e:
    print(f'❌ Error creating test user: {e}')
    exit(1)
"; then
    print_success "User creation test passed"
else
    print_error "User creation test failed"
    exit 1
fi

print_success "🎉 CustomUser relation fix completed successfully!"
echo
print_status "Summary of actions taken:"
echo "  ✓ Backed up existing migrations to $BACKUP_DIR"
echo "  ✓ Removed problematic migration files"
echo "  ✓ Reset migration state"
echo "  ✓ Created fresh CustomUser migrations"
echo "  ✓ Applied all migrations successfully"
echo "  ✓ Verified database table creation"
echo "  ✓ Tested user model functionality"
echo
print_status "Your Django project should now work without the 'core_users_customuser does not exist' error."
print_status "You can now run your Django commands normally."

# Optional: Create a superuser
echo
read -p "Do you want to create a superuser account now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Creating superuser..."
    if [ -f "scripts/create_superuser.sh" ]; then
        bash scripts/create_superuser.sh
    else
        run_django_cmd createsuperuser
    fi
fi

print_success "🚀 All done! Your Django application is ready to use."
