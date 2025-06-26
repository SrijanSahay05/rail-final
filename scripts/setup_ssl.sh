#!/bin/bash

# SSL Certificate Setup Script using Let's Encrypt
# This script sets up SSL certificates for production Django deployment

echo "🔒 SSL Certificate Setup for Production"
echo "======================================"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "This script needs to be run as root for SSL certificate setup"
        print_status "Please run: sudo $0"
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if domain is provided
    if [ -z "$DOMAIN" ]; then
        print_error "Domain not provided"
        echo "Usage: sudo DOMAIN=yourdomain.com $0"
        echo "Example: sudo DOMAIN=myapp.example.com $0"
        exit 1
    fi
    
    # Check if certbot is installed
    if ! command -v certbot &> /dev/null; then
        print_status "Installing certbot..."
        apt-get update
        apt-get install -y certbot
    fi
    
    print_success "Prerequisites checked"
}

# Create SSL directories
create_ssl_directories() {
    print_status "Creating SSL directories..."
    
    mkdir -p nginx/ssl
    mkdir -p nginx/certbot-challenges
    
    print_success "SSL directories created"
}

# Generate Let's Encrypt certificates
generate_letsencrypt_certificates() {
    print_status "Generating Let's Encrypt certificates for domain: $DOMAIN"
    
    # Stop nginx if running to avoid port conflicts
    print_status "Stopping nginx temporarily..."
    docker-compose -f docker-compose.prod.yml stop nginx 2>/dev/null || true
    
    # Generate certificate using standalone mode
    if certbot certonly \
        --standalone \
        --preferred-challenges http \
        --email admin@$DOMAIN \
        --agree-tos \
        --no-eff-email \
        -d $DOMAIN; then
        
        print_success "Let's Encrypt certificates generated successfully"
        
        # Copy certificates to nginx directory
        print_status "Copying certificates to nginx directory..."
        cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem nginx/ssl/nginx.crt
        cp /etc/letsencrypt/live/$DOMAIN/privkey.pem nginx/ssl/nginx.key
        
        # Set proper permissions
        chmod 644 nginx/ssl/nginx.crt
        chmod 600 nginx/ssl/nginx.key
        
        print_success "Certificates copied to nginx/ssl/"
        
    else
        print_error "Failed to generate Let's Encrypt certificates"
        print_status "Falling back to self-signed certificates..."
        generate_self_signed_certificates
    fi
}

# Generate self-signed certificates (for development/testing)
generate_self_signed_certificates() {
    print_status "Generating self-signed SSL certificates..."
    
    # Create SSL directory if it doesn't exist
    mkdir -p nginx/ssl
    
    # Generate self-signed certificate
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout nginx/ssl/nginx.key \
        -out nginx/ssl/nginx.crt \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=$DOMAIN"
    
    print_success "Self-signed certificates generated"
    print_warning "Self-signed certificates are not trusted by browsers"
    print_warning "Use Let's Encrypt for production!"
}

# Update nginx configuration for SSL
update_nginx_config() {
    print_status "Updating nginx configuration for SSL..."
    
    # Check if nginx.prod.conf exists
    if [ ! -f "nginx/nginx.prod.conf" ]; then
        print_error "nginx/nginx.prod.conf not found"
        exit 1
    fi
    
    # Update server_name in nginx config
    sed -i "s/server_name localhost;/server_name $DOMAIN;/g" nginx/nginx.prod.conf
    
    print_success "Nginx configuration updated for domain: $DOMAIN"
}

# Update docker-compose for SSL
update_docker_compose_ssl() {
    print_status "Updating docker-compose.prod.yml for SSL..."
    
    # Create a backup
    cp docker-compose.prod.yml docker-compose.prod.yml.backup
    
    # Update nginx service to use production config and SSL
    cat > docker-compose.prod.yml << EOF
services:
  db:
    image: postgres:15
    env_file:
      - .env.prod
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always
    ports:
      - "5432:5432"

  web:
    build:
      context: .
      dockerfile: dockerfile.prod
    command: >
      sh -c "python manage.py collectstatic --noinput &&
         python manage.py makemigrations &&
         python manage.py migrate &&
         gunicorn core.wsgi:application --bind 0.0.0.0:8000 --workers 3"
    volumes:
      - .:/app
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    env_file:
      - .env.prod
    depends_on:
      - db
    restart: unless-stopped
    expose:
      - "8000"
  
  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.prod.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    depends_on:
      - web
    restart: always

volumes:
  postgres_data:
  static_volume:
  media_volume:
EOF
    
    print_success "Docker Compose configuration updated for SSL"
}

# Set up certificate renewal
setup_certificate_renewal() {
    print_status "Setting up automatic certificate renewal..."
    
    # Create renewal script
    cat > /usr/local/bin/renew-ssl-certificates.sh << EOF
#!/bin/bash
# SSL Certificate Renewal Script

DOMAIN=$DOMAIN
PROJECT_DIR=$(pwd)

# Stop nginx
cd \$PROJECT_DIR
docker-compose -f docker-compose.prod.yml stop nginx

# Renew certificates
certbot renew --standalone

# Copy renewed certificates
cp /etc/letsencrypt/live/\$DOMAIN/fullchain.pem nginx/ssl/nginx.crt
cp /etc/letsencrypt/live/\$DOMAIN/privkey.pem nginx/ssl/nginx.key

# Set proper permissions
chmod 644 nginx/ssl/nginx.crt
chmod 600 nginx/ssl/nginx.key

# Restart nginx
docker-compose -f docker-compose.prod.yml start nginx

echo "SSL certificates renewed successfully"
EOF
    
    chmod +x /usr/local/bin/renew-ssl-certificates.sh
    
    # Add cron job for automatic renewal (runs twice daily)
    (crontab -l 2>/dev/null; echo "0 2,14 * * * /usr/local/bin/renew-ssl-certificates.sh >> /var/log/ssl-renewal.log 2>&1") | crontab -
    
    print_success "Automatic certificate renewal configured"
    print_status "Certificates will be renewed automatically twice daily"
}

# Main function
main() {
    print_status "Starting SSL certificate setup..."
    
    check_root
    check_prerequisites
    create_ssl_directories
    
    # Ask user for certificate type
    echo ""
    print_status "Choose certificate type:"
    echo "1) Let's Encrypt (Recommended for production)"
    echo "2) Self-signed (Development/Testing only)"
    read -p "Enter your choice (1 or 2): " -n 1 -r
    echo
    
    case $REPLY in
        1)
            generate_letsencrypt_certificates
            setup_certificate_renewal
            ;;
        2)
            generate_self_signed_certificates
            ;;
        *)
            print_error "Invalid choice"
            exit 1
            ;;
    esac
    
    update_nginx_config
    update_docker_compose_ssl
    
    print_success "🎉 SSL setup completed!"
    echo ""
    print_status "Next steps:"
    echo "1. Update your .env.prod file with your domain"
    echo "2. Start your services: ./scripts/prod_setup.sh start"
    echo "3. Your site will be available at: https://$DOMAIN"
    echo ""
    print_warning "Don't forget to:"
    echo "- Point your domain DNS to this server's IP"
    echo "- Open ports 80 and 443 in your firewall"
    echo "- Update ALLOWED_HOSTS in .env.prod to include $DOMAIN"
}

# Check if domain is provided as environment variable
if [ -z "$DOMAIN" ]; then
    echo "Usage: sudo DOMAIN=yourdomain.com $0"
    echo "Example: sudo DOMAIN=myapp.example.com $0"
    exit 1
fi

main
