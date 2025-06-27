#!/bin/bash

# Server-side SSL Setup Script for srijansahay05.in
# This script sets up Certbot directly on the server (not in container)

echo "🔒 Setting up SSL certificates on server for srijansahay05.in"
echo "============================================================"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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
if [ "$EUID" -ne 0 ]; then
    print_error "This script must be run as root"
    print_status "Please run: sudo $0"
    exit 1
fi

# Variables
DOMAIN="srijansahay05.in"
EMAIL="admin@srijansahay05.in"
PROJECT_DIR="/home/$(logname)/Developer/dvm_recruitments/rail-final"  # Adjust path as needed

print_status "Starting server-side SSL setup for $DOMAIN"

# Step 1: Install Certbot
print_status "Installing Certbot..."
apt update
apt install -y certbot

print_success "Certbot installed"

# Step 2: Create webroot directory
print_status "Creating webroot directory for challenges..."
mkdir -p "$PROJECT_DIR/certbot-www"
chown -R $(logname):$(logname) "$PROJECT_DIR/certbot-www"

print_success "Webroot directory created at $PROJECT_DIR/certbot-www"

# Step 3: Generate SSL certificate
print_status "Generating SSL certificate for $DOMAIN..."

if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    print_warning "SSL certificate already exists for $DOMAIN"
else
    print_status "Starting temporary HTTP server for domain validation..."
    
    # Stop any running containers that might be using port 80
    cd "$PROJECT_DIR"
    docker-compose -f docker-compose.prod.yml stop nginx 2>/dev/null || true
    
    # Generate certificate using standalone mode (since nginx isn't running yet)
    certbot certonly \
        --standalone \
        --preferred-challenges http \
        --email "$EMAIL" \
        --agree-tos \
        --no-eff-email \
        -d "$DOMAIN"
    
    if [ $? -eq 0 ]; then
        print_success "SSL certificate generated successfully for $DOMAIN"
    else
        print_error "Failed to generate SSL certificate"
        exit 1
    fi
fi

# Step 4: Set up automatic renewal
print_status "Setting up automatic certificate renewal..."

# Create renewal script
cat > /usr/local/bin/renew-ssl-srijansahay05.sh << EOF
#!/bin/bash
# SSL Certificate Renewal Script for srijansahay05.in

DOMAIN="$DOMAIN"
PROJECT_DIR="$PROJECT_DIR"
LOG_FILE="/var/log/ssl-renewal-\$DOMAIN.log"

echo "\$(date): Starting SSL renewal for \$DOMAIN" >> \$LOG_FILE

# Stop nginx container temporarily
cd "\$PROJECT_DIR"
docker-compose -f docker-compose.prod.yml stop nginx >> \$LOG_FILE 2>&1

# Renew certificate
certbot renew --quiet >> \$LOG_FILE 2>&1

if [ \$? -eq 0 ]; then
    echo "\$(date): SSL certificate renewed successfully" >> \$LOG_FILE
else
    echo "\$(date): SSL certificate renewal failed" >> \$LOG_FILE
fi

# Restart nginx container
docker-compose -f docker-compose.prod.yml start nginx >> \$LOG_FILE 2>&1

echo "\$(date): SSL renewal process completed" >> \$LOG_FILE
EOF

chmod +x /usr/local/bin/renew-ssl-srijansahay05.sh

# Add cron job for automatic renewal (runs twice daily)
(crontab -l 2>/dev/null | grep -v "renew-ssl-srijansahay05.sh"; echo "0 2,14 * * * /usr/local/bin/renew-ssl-srijansahay05.sh") | crontab -

print_success "Automatic renewal configured (runs twice daily at 2 AM and 2 PM)"

# Step 5: Set proper permissions
print_status "Setting proper permissions for certificates..."
chmod 755 /etc/letsencrypt/live/
chmod 755 /etc/letsencrypt/archive/
chmod 644 /etc/letsencrypt/live/$DOMAIN/fullchain.pem
chmod 600 /etc/letsencrypt/live/$DOMAIN/privkey.pem

print_success "Certificate permissions set"

# Step 6: Display final instructions
print_success "🎉 Server-side SSL setup completed!"
echo ""
print_status "SSL certificate information:"
echo "  Domain: $DOMAIN"
echo "  Certificate: /etc/letsencrypt/live/$DOMAIN/fullchain.pem"
echo "  Private Key: /etc/letsencrypt/live/$DOMAIN/privkey.pem"
echo "  Webroot: $PROJECT_DIR/certbot-www"
echo ""
print_status "Next steps:"
echo "1. Start your Docker containers: cd $PROJECT_DIR && ./scripts/prod_setup.sh start"
echo "2. Your site will be available at: https://$DOMAIN"
echo ""
print_status "Certificate renewal:"
echo "  • Automatic renewal is configured via cron job"
echo "  • Manual renewal: sudo certbot renew"
echo "  • Check renewal logs: tail -f /var/log/ssl-renewal-$DOMAIN.log"
echo ""
print_warning "Make sure your domain DNS points to this server's IP address!"
