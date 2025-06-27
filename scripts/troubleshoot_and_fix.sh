#!/bin/bash

# Django Railway System - Troubleshooting and Fix Script
# This script detects and fixes common issues with the Docker setup

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

# Function to get compose file path
get_compose_file() {
    local env=$(get_environment)
    if [ "$env" = "dev" ]; then
        echo "docker-compose.dev.yml"
    elif [ "$env" = "prod" ]; then
        echo "docker-compose.prod.yml"
    else
        echo ""
    fi
}

# Function to check for port conflicts
check_port_conflicts() {
    print_status "Checking for port conflicts..."
    
    local compose_file=$(get_compose_file)
    local ports=()
    
    # Extract ports from docker-compose file
    if [ -f "$compose_file" ]; then
        ports=($(grep -E "ports:" -A 10 "$compose_file" | grep -E "^\s*- \"[0-9]+:[0-9]+\"" | sed 's/.*"\([0-9]*\):.*/\1/' | sort -u))
    fi
    
    local conflicts=()
    
    for port in "${ports[@]}"; do
        if lsof -i ":$port" > /dev/null 2>&1; then
            conflicts+=("$port")
        fi
    done
    
    if [ ${#conflicts[@]} -gt 0 ]; then
        print_warning "Port conflicts detected on ports: ${conflicts[*]}"
        return 1
    else
        print_success "No port conflicts detected"
        return 0
    fi
}

# Function to fix port conflicts
fix_port_conflicts() {
    print_status "Attempting to fix port conflicts..."
    
    local compose_file=$(get_compose_file)
    
    # Stop all containers from this project
    print_status "Stopping all project containers..."
    docker-compose -f "$compose_file" down 2>/dev/null || true
    
    # Stop any containers that might be using the ports
    print_status "Checking for containers using required ports..."
    
    # Check for containers using port 5432 (PostgreSQL)
    local postgres_containers=$(docker ps -q --filter "publish=5432")
    if [ ! -z "$postgres_containers" ]; then
        print_warning "Found containers using port 5432:"
        docker ps --filter "publish=5432"
        read -p "Do you want to stop these containers? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker stop $postgres_containers
            print_success "Stopped containers using port 5432"
        fi
    fi
    
    # Check for containers using port 80 (Nginx)
    local nginx_containers=$(docker ps -q --filter "publish=80")
    if [ ! -z "$nginx_containers" ]; then
        print_warning "Found containers using port 80:"
        docker ps --filter "publish=80"
        read -p "Do you want to stop these containers? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker stop $nginx_containers
            print_success "Stopped containers using port 80"
        fi
    fi
    
    # Check for containers using port 8000 (Django)
    local django_containers=$(docker ps -q --filter "publish=8000")
    if [ ! -z "$django_containers" ]; then
        print_warning "Found containers using port 8000:"
        docker ps --filter "publish=8000"
        read -p "Do you want to stop these containers? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker stop $django_containers
            print_success "Stopped containers using port 8000"
        fi
    fi
}

# Function to check and fix environment files
check_environment_files() {
    print_status "Checking environment files..."
    
    local env=$(get_environment)
    local env_file=".env.$env"
    
    if [ ! -f "$env_file" ]; then
        print_warning "Environment file $env_file not found. Creating it..."
        if [ "$env" = "dev" ]; then
            cat > "$env_file" << EOF
# Django settings
DJANGO_SECRET_KEY=dev-secret-key-change-in-production-$(date +%s)
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
        elif [ "$env" = "prod" ]; then
            cat > "$env_file" << EOF
# Django settings
DJANGO_SECRET_KEY=prod-secret-key-change-in-production-$(date +%s)
DEBUG=False

# Database settings
POSTGRES_DB=django_prod
POSTGRES_USER=postgres_user
POSTGRES_PASSWORD=postgres_password
DB_HOST=db
DB_PORT=5432

# Django allowed hosts
ALLOWED_HOSTS=your-production-domain.com,localhost,127.0.0.1,web,nginx

# Security settings for production
SECURE_SSL_REDIRECT=False
SECURE_HSTS_SECONDS=0
SECURE_HSTS_INCLUDE_SUBDOMAINS=False
SECURE_HSTS_PRELOAD=False
SECURE_CONTENT_TYPE_NOSNIFF=False
SECURE_BROWSER_XSS_FILTER=False
SECURE_REFERRER_POLICY=same-origin
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
X_FRAME_OPTIONS=DENY

# Add your API keys here
GOOGLE_OAUTH2_CLIENT_ID=your-client-id
GOOGLE_OAUTH2_CLIENT_SECRET=your-client-secret
EOF
        fi
        print_success "Created $env_file"
    else
        print_success "Environment file $env_file exists"
    fi
}

# Function to check and fix migration issues
check_migration_issues() {
    print_status "Checking for migration issues..."
    
    local compose_file=$(get_compose_file)
    
    # Check if containers are running
    if ! docker-compose -f "$compose_file" ps | grep -q "Up"; then
        print_warning "Containers are not running. Starting them first..."
        docker-compose -f "$compose_file" up -d db
        sleep 10
        docker-compose -f "$compose_file" up -d web
        sleep 15
    fi
    
    # Try to run a simple Django command to check for migration issues
    if docker-compose -f "$compose_file" exec web python manage.py check --database default 2>&1 | grep -q "relation.*does not exist"; then
        print_warning "Migration issues detected. Running migration fix..."
        return 1
    fi
    
    print_success "No migration issues detected"
    return 0
}

# Function to fix migration issues
fix_migration_issues() {
    print_status "Fixing migration issues..."
    
    local compose_file=$(get_compose_file)
    
    # Stop containers
    docker-compose -f "$compose_file" down
    
    # Remove existing migration files except __init__.py
    print_status "Removing existing migration files..."
    find . -path "*/migrations/*.py" ! -name "__init__.py" -delete 2>/dev/null || true
    find . -path "*/migrations/*.pyc" -delete 2>/dev/null || true
    
    # Create migration directories
    print_status "Creating migration directories..."
    mkdir -p core_users/migrations
    mkdir -p core_home/migrations
    mkdir -p feature_railways/migrations
    mkdir -p feature_transaction/migrations
    
    touch core_users/migrations/__init__.py
    touch core_home/migrations/__init__.py
    touch feature_railways/migrations/__init__.py
    touch feature_transaction/migrations/__init__.py
    
    # Start database
    docker-compose -f "$compose_file" up -d db
    sleep 10
    
    # Start web service
    docker-compose -f "$compose_file" up -d web
    sleep 15
    
    # Create migrations for core_users first
    print_status "Creating migrations for core_users..."
    docker-compose -f "$compose_file" exec web python manage.py makemigrations core_users
    
    # Create migrations for all other apps
    print_status "Creating migrations for all other apps..."
    docker-compose -f "$compose_file" exec web python manage.py makemigrations
    
    # Apply migrations
    print_status "Applying migrations..."
    docker-compose -f "$compose_file" exec web python manage.py migrate
    
    print_success "Migration issues fixed"
}

# Function to check and fix Docker issues
check_docker_issues() {
    print_status "Checking Docker issues..."
    
    # Check Docker daemon
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker daemon is not running"
        return 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "docker-compose is not installed"
        return 1
    fi
    
    # Check available disk space
    local available_space=$(df . | awk 'NR==2 {print $4}')
    if [ "$available_space" -lt 1000000 ]; then
        print_warning "Low disk space available: ${available_space}KB"
        return 1
    fi
    
    print_success "Docker environment is healthy"
    return 0
}

# Function to clean up Docker resources
cleanup_docker_resources() {
    print_status "Cleaning up Docker resources..."
    
    # Remove stopped containers
    docker container prune -f
    
    # Remove unused networks
    docker network prune -f
    
    # Remove unused images
    docker image prune -f
    
    # Remove unused volumes (be careful with this in production)
    if [ "$1" = "aggressive" ]; then
        print_warning "Performing aggressive cleanup (removing volumes)..."
        docker volume prune -f
    fi
    
    print_success "Docker cleanup completed"
}

# Function to rebuild containers
rebuild_containers() {
    print_status "Rebuilding containers..."
    
    local compose_file=$(get_compose_file)
    
    # Stop containers
    docker-compose -f "$compose_file" down
    
    # Remove images
    docker-compose -f "$compose_file" down --rmi all
    
    # Rebuild
    docker-compose -f "$compose_file" build --no-cache
    
    print_success "Containers rebuilt"
}

# Function to run Django commands safely
run_django_command() {
    local compose_file=$(get_compose_file)
    local command="$1"
    
    print_status "Running Django command: $command"
    
    if docker-compose -f "$compose_file" ps | grep -q "Up"; then
        docker-compose -f "$compose_file" exec web python manage.py "$command"
    else
        print_error "Containers are not running. Please start them first."
        return 1
    fi
}

# Function to show system status
show_system_status() {
    print_status "System Status Report"
    echo "======================"
    
    local compose_file=$(get_compose_file)
    local env=$(get_environment)
    
    echo "Environment: $env"
    echo "Compose file: $compose_file"
    echo ""
    
    echo "Docker Status:"
    docker info --format "{{.ServerVersion}}" 2>/dev/null || echo "Docker not running"
    echo ""
    
    echo "Container Status:"
    if [ -f "$compose_file" ]; then
        docker-compose -f "$compose_file" ps
    else
        echo "No compose file found"
    fi
    echo ""
    
    echo "Port Usage:"
    lsof -i :5432 2>/dev/null | head -5 || echo "Port 5432: Available"
    lsof -i :80 2>/dev/null | head -5 || echo "Port 80: Available"
    lsof -i :8000 2>/dev/null | head -5 || echo "Port 8000: Available"
    echo ""
    
    echo "Disk Space:"
    df -h . | head -2
    echo ""
    
    echo "Recent Logs (last 10 lines):"
    if [ -f "$compose_file" ]; then
        docker-compose -f "$compose_file" logs --tail=10
    else
        echo "No compose file found"
    fi
}

# Main function
main() {
    echo "🔧 Django Railway System - Troubleshooting and Fix Script"
    echo "========================================================="
    
    # Check prerequisites
    check_django_project
    check_docker_environment
    
    local env=$(get_environment)
    local compose_file=$(get_compose_file)
    
    print_status "Using $env environment with $compose_file"
    
    # Check and fix environment files
    check_environment_files
    
    # Check Docker issues
    if ! check_docker_issues; then
        print_error "Docker issues detected. Please fix them manually."
        exit 1
    fi
    
    # Check for port conflicts
    if ! check_port_conflicts; then
        print_warning "Port conflicts detected. Attempting to fix..."
        fix_port_conflicts
    fi
    
    # Check migration issues
    if ! check_migration_issues; then
        print_warning "Migration issues detected. Attempting to fix..."
        fix_migration_issues
    fi
    
    print_success "Troubleshooting completed successfully!"
}

# Handle command line arguments
case "$1" in
    "check")
        echo "🔍 Running diagnostic checks..."
        check_django_project
        check_docker_environment
        check_port_conflicts
        check_migration_issues
        print_success "Diagnostic checks completed"
        ;;
    "fix-ports")
        echo "🔧 Fixing port conflicts..."
        fix_port_conflicts
        ;;
    "fix-migrations")
        echo "🔧 Fixing migration issues..."
        fix_migration_issues
        ;;
    "cleanup")
        echo "🧹 Cleaning up Docker resources..."
        cleanup_docker_resources "$2"
        ;;
    "rebuild")
        echo "🔨 Rebuilding containers..."
        rebuild_containers
        ;;
    "status")
        show_system_status
        ;;
    "django")
        if [ -z "$2" ]; then
            print_error "Please specify a Django command"
            echo "Usage: $0 django <command>"
            exit 1
        fi
        run_django_command "$2"
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  (no args)     - Run full troubleshooting and fix process"
        echo "  check         - Run diagnostic checks only"
        echo "  fix-ports     - Fix port conflicts"
        echo "  fix-migrations - Fix migration issues"
        echo "  cleanup       - Clean up Docker resources"
        echo "  rebuild       - Rebuild containers"
        echo "  status        - Show system status"
        echo "  django <cmd>  - Run Django command"
        echo "  help          - Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0                    # Full troubleshooting"
        echo "  $0 check              # Run diagnostics"
        echo "  $0 fix-migrations     # Fix migration issues"
        echo "  $0 django shell       # Open Django shell"
        echo "  $0 django createsuperuser # Create superuser"
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