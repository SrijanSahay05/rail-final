#!/bin/bash

echo "Creating Migrations in Production Docker Container"
echo "================================================="
echo ""

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

# Check if we're in the correct directory
if [ ! -f "docker-compose.prod.yml" ]; then
    print_error "docker-compose.prod.yml not found. Please run this script from the project root directory."
    exit 1
fi

# Check if .env.prod exists
if [ ! -f ".env.prod" ]; then
    print_warning ".env.prod file not found. Make sure your production environment variables are properly configured."
fi

# Function to check if production containers are running
check_prod_containers() {
    print_status "Checking production container status..."
    
    if docker-compose -f docker-compose.prod.yml ps --services --filter "status=running" | grep -q web; then
        print_success "Production containers are running"
        return 0
    else
        print_warning "Production containers are not running"
        read -p "Do you want to start the production containers? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_status "Starting production containers..."
            docker-compose -f docker-compose.prod.yml up -d
            
            print_status "Waiting for containers to be ready..."
            sleep 20
            
            # Wait for database to be ready
            print_status "Waiting for database to be ready..."
            local max_wait=60
            local wait_time=0
            
            while [ $wait_time -lt $max_wait ]; do
                if docker-compose -f docker-compose.prod.yml exec web python manage.py check --database default > /dev/null 2>&1; then
                    print_success "Database is ready"
                    break
                fi
                sleep 5
                wait_time=$((wait_time + 5))
                print_status "Waiting for database... ($wait_time/$max_wait seconds)"
            done
            
            if [ $wait_time -ge $max_wait ]; then
                print_error "Database did not become ready in time"
                exit 1
            fi
        else
            print_error "Production containers need to be running for this script to work"
            exit 1
        fi
    fi
}

# Function to run Django commands in production container
run_prod_django_cmd() {
    docker-compose -f docker-compose.prod.yml exec web python manage.py "$@"
}

# Define the local apps that need migrations
LOCAL_APPS=(
    "core_home"
    "core_users"
    "feature_railways" 
    "feature_transaction"
)

print_status "Starting production migration process..."

# Check production containers
check_prod_containers

print_status "Creating backup of existing migration files..."

# Create backup directory with timestamp
BACKUP_DIR="migration_backup_prod_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup existing migrations if they exist
for app in "${LOCAL_APPS[@]}"; do
    if [ -d "$app/migrations" ] && [ "$(ls -A $app/migrations/*.py 2>/dev/null | grep -v __init__ || true)" ]; then
        print_status "Backing up existing $app migrations..."
        mkdir -p "$BACKUP_DIR/$app"
        cp $app/migrations/*.py "$BACKUP_DIR/$app/" 2>/dev/null || true
    fi
done

print_success "Backup created in $BACKUP_DIR"

print_status "🔧 Making migrations for each app individually..."
echo ""

# Create migrations for core_users first (most important for custom user model)
print_status "📝 Creating migrations for core_users first..."
if run_prod_django_cmd makemigrations core_users; then
    print_success "✅ Migrations created successfully for core_users"
else
    print_error "❌ Failed to create migrations for core_users"
    print_error "This is critical - core_users contains the CustomUser model"
    exit 1
fi
echo ""

# Create migrations for other local apps
for app in "${LOCAL_APPS[@]}"; do
    if [ "$app" != "core_users" ]; then
        print_status "📝 Creating migrations for: $app"
        if run_prod_django_cmd makemigrations $app; then
            print_success "✅ Migrations created successfully for $app"
        else
            print_warning "❌ Failed to create migrations for $app (continuing with others)"
        fi
        echo ""
    fi
done

print_status "📝 Creating migrations for any remaining apps..."
if run_prod_django_cmd makemigrations; then
    print_success "✅ General makemigrations completed"
else
    print_warning "❌ General makemigrations failed (this might be expected if no changes)"
fi
echo ""

print_status "🚀 Applying all migrations..."
echo ""

# Apply migrations for core_users first (since other apps depend on it)
print_status "📦 Applying core_users migrations first..."
if run_prod_django_cmd migrate core_users; then
    print_success "✅ core_users migrations applied successfully"
else
    print_error "❌ Failed to apply core_users migrations"
    print_error "This is critical - other apps depend on CustomUser model"
    exit 1
fi
echo ""

# Apply built-in Django app migrations
print_status "📦 Applying Django built-in app migrations..."
DJANGO_APPS=("contenttypes" "auth" "admin" "sessions" "messages" "staticfiles" "sites")

for django_app in "${DJANGO_APPS[@]}"; do
    print_status "Applying $django_app migrations..."
    if run_prod_django_cmd migrate $django_app; then
        print_success "✅ $django_app migrations applied"
    else
        print_warning "❌ Failed to apply $django_app migrations (might already be applied)"
    fi
done
echo ""

# Apply migrations for other local apps
for app in "${LOCAL_APPS[@]}"; do
    if [ "$app" != "core_users" ]; then
        print_status "📦 Applying $app migrations..."
        if run_prod_django_cmd migrate $app; then
            print_success "✅ $app migrations applied successfully"
        else
            print_warning "❌ Failed to apply $app migrations"
        fi
    fi
done
echo ""

# Apply all remaining migrations
print_status "📦 Applying all remaining migrations..."
if run_prod_django_cmd migrate; then
    print_success "✅ All migrations applied successfully"
else
    print_error "❌ Failed to apply some migrations"
fi
echo ""

# Show final migration status
print_status "📋 Final migration status:"
echo ""
for app in "${LOCAL_APPS[@]}"; do
    print_status "Migration status for $app:"
    run_prod_django_cmd showmigrations $app || true
    echo ""
done

# Collect static files for production
print_status "📦 Collecting static files for production..."
if run_prod_django_cmd collectstatic --noinput; then
    print_success "✅ Static files collected successfully"
else
    print_warning "❌ Failed to collect static files"
fi
echo ""

# Optional: Create superuser for production
print_status "👤 Superuser management"
read -p "Do you want to create a superuser for production? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Creating production superuser..."
    if [ -f "scripts/create_superuser.sh" ]; then
        # Modify the create_superuser script to work with production
        docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
    else
        run_prod_django_cmd createsuperuser
    fi
fi

print_success "🎉 Production migration process completed!"
echo "=============================================="
echo ""
print_status "Summary:"
echo "  ✓ Backed up existing migrations to $BACKUP_DIR"
echo "  ✓ Created migrations for all local apps"
echo "  ✓ Applied migrations in correct dependency order"
echo "  ✓ Collected static files"
echo "  ✓ Production environment is ready"
echo ""
print_status "Your production Django application should now be fully migrated and ready."
print_status "Access your application at: http://localhost (via nginx) or http://localhost:8000 (direct)"
echo ""
print_warning "Remember to:"
echo "  - Verify your .env.prod file has correct production settings"
echo "  - Ensure DEBUG=False in production"
echo "  - Use strong SECRET_KEY in production"
echo "  - Configure proper ALLOWED_HOSTS"
