# Django Railway System - Docker Setup Guide

This guide provides comprehensive instructions for setting up and managing the Django Railway System using Docker for both development and production environments.

## 🚀 Quick Start

### Development Environment
```bash
# First time setup
./scripts/dev_setup.sh

# Start services
./scripts/dev_setup.sh start

# Stop services
./scripts/dev_setup.sh stop
```

### Production Environment
```bash
# First time setup
./scripts/prod_setup.sh

# Start services
./scripts/prod_setup.sh start

# Stop services
./scripts/prod_setup.sh stop
```

## 📁 Project Structure

```
railway-system-v3/
├── docker-compose.dev.yml      # Development Docker Compose
├── docker-compose.prod.yml     # Production Docker Compose
├── dockerfile.dev              # Development Dockerfile
├── dockerfile.prod             # Production Dockerfile
├── scripts/
│   ├── dev_setup.sh            # Development environment management
│   ├── prod_setup.sh           # Production environment management
│   └── fix_initial_migrations.sh # Migration fix script
├── nginx/
│   ├── nginx.dev.conf          # Development Nginx config
│   └── nginx.prod.conf         # Production Nginx config
└── .env.dev/.env.prod          # Environment files
```

## 🔧 Development Environment

### Prerequisites
- Docker and Docker Compose installed
- Git (for cloning the repository)

### Setup Commands

| Command | Description |
|---------|-------------|
| `./scripts/dev_setup.sh` | Full development setup (first time) |
| `./scripts/dev_setup.sh start` | Start development services |
| `./scripts/dev_setup.sh stop` | Stop development services |
| `./scripts/dev_setup.sh restart` | Restart development services |
| `./scripts/dev_setup.sh logs` | View service logs |
| `./scripts/dev_setup.sh shell` | Open Django shell |
| `./scripts/dev_setup.sh superuser` | Create Django superuser |
| `./scripts/dev_setup.sh migrate` | Run Django migrations |
| `./scripts/dev_setup.sh fix-migrations` | Fix migration issues |
| `./scripts/dev_setup.sh collect-static` | Collect static files |
| `./scripts/dev_setup.sh flush` | Flush database (delete all data) |
| `./scripts/dev_setup.sh clean` | Clean up containers and volumes |
| `./scripts/dev_setup.sh status` | Show container status |

### Development URLs
- **Main Application**: http://localhost (via Nginx)
- **Django Direct**: http://localhost:8000
- **Database**: localhost:5432

## 🏭 Production Environment

### Prerequisites
- Docker and Docker Compose installed
- Domain name configured (for production)
- SSL certificates (optional, for HTTPS)

### Setup Commands

| Command | Description |
|---------|-------------|
| `./scripts/prod_setup.sh` | Full production setup (first time) |
| `./scripts/prod_setup.sh start` | Start production services |
| `./scripts/prod_setup.sh stop` | Stop production services |
| `./scripts/prod_setup.sh restart` | Restart production services |
| `./scripts/prod_setup.sh logs` | View service logs |
| `./scripts/prod_setup.sh shell` | Open Django shell |
| `./scripts/prod_setup.sh superuser` | Create Django superuser |
| `./scripts/prod_setup.sh migrate` | Run Django migrations |
| `./scripts/prod_setup.sh fix-migrations` | Fix migration issues |
| `./scripts/prod_setup.sh collect-static` | Collect static files |
| `./scripts/prod_setup.sh flush` | Flush database (delete all data) |
| `./scripts/prod_setup.sh clean` | Clean up containers and volumes |
| `./scripts/prod_setup.sh status` | Show container status |

### Production URLs
- **Main Application**: http://localhost (via Nginx)
- **Django Direct**: http://localhost:8000
- **Database**: localhost:5432

## 🔄 Migration Management

### Fix Initial Migrations
If you encounter migration issues, especially with the custom user model, use the dedicated migration fix script:

```bash
./scripts/fix_initial_migrations.sh
```

This script will:
1. Remove all existing migration files
2. Create fresh migration directories
3. Create migrations for `core_users` first (AUTH_USER_MODEL)
4. Create migrations for all other apps
5. Apply `core_users` migrations first
6. Apply all remaining migrations
7. Collect static files

### Manual Migration Commands
```bash
# Development
./scripts/dev_setup.sh migrate

# Production
./scripts/prod_setup.sh migrate

# Fix migrations (removes existing migrations)
./scripts/dev_setup.sh fix-migrations
./scripts/prod_setup.sh fix-migrations
```

## 🛠️ Environment Configuration

### Development Environment (.env.dev)
```bash
# Django settings
DJANGO_SECRET_KEY=dev-secret-key-change-in-production-1234567890
DEBUG=True

# Database settings
POSTGRES_DB=django_dev
POSTGRES_USER=postgres_user
POSTGRES_PASSWORD=postgres_password
DB_HOST=db
DB_PORT=5432

# Django allowed hosts
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,web,nginx

# API keys
GOOGLE_OAUTH2_CLIENT_ID=your-client-id
GOOGLE_OAUTH2_CLIENT_SECRET=your-client-secret
```

### Production Environment (.env.prod)
```bash
# Django settings
DJANGO_SECRET_KEY=your-strong-production-secret-key
DEBUG=False

# Database settings
POSTGRES_DB=django_prod
POSTGRES_USER=postgres_user
POSTGRES_PASSWORD=strong-production-password
DB_HOST=db
DB_PORT=5432

# Django allowed hosts
ALLOWED_HOSTS=your-domain.com,localhost,127.0.0.1,web,nginx

# Security settings
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

# API keys
GOOGLE_OAUTH2_CLIENT_ID=your-client-id
GOOGLE_OAUTH2_CLIENT_SECRET=your-client-secret
```

## 🔒 Security Checklist (Production)

Before deploying to production, ensure:

- [ ] `DEBUG=False` in `.env.prod`
- [ ] Strong `DJANGO_SECRET_KEY` is set
- [ ] Proper `ALLOWED_HOSTS` configured
- [ ] Secure database credentials
- [ ] SSL/HTTPS configured (if needed)
- [ ] Review security settings in `.env.prod`

## 🐳 Docker Services

### Development Services
- **db**: PostgreSQL 15 database
- **web**: Django development server
- **nginx**: Reverse proxy

### Production Services
- **db**: PostgreSQL 15 database
- **web**: Gunicorn WSGI server
- **nginx**: Reverse proxy with SSL support

## 📊 Monitoring and Logs

### View Logs
```bash
# Development
./scripts/dev_setup.sh logs

# Production
./scripts/prod_setup.sh logs
```

### Check Service Status
```bash
# Development
./scripts/dev_setup.sh status

# Production
./scripts/prod_setup.sh status
```

## 🧹 Maintenance

### Clean Up
```bash
# Development (removes all data)
./scripts/dev_setup.sh clean

# Production (removes all data)
./scripts/prod_setup.sh clean
```

### Database Operations
```bash
# Flush database (delete all data)
./scripts/dev_setup.sh flush
./scripts/prod_setup.sh flush

# Create superuser
./scripts/dev_setup.sh superuser
./scripts/prod_setup.sh superuser
```

## 🚨 Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Stop all containers
   ./scripts/dev_setup.sh stop
   ./scripts/prod_setup.sh stop
   
   # Check what's using the port
   lsof -i :8000
   lsof -i :80
   ```

2. **Migration Issues**
   ```bash
   # Use the migration fix script
   ./scripts/fix_initial_migrations.sh
   ```

3. **Database Connection Issues**
   ```bash
   # Restart services
   ./scripts/dev_setup.sh restart
   ./scripts/prod_setup.sh restart
   ```

4. **Permission Issues**
   ```bash
   # Make scripts executable
   chmod +x scripts/*.sh
   ```

### Health Checks
The Docker Compose files include health checks for all services. If services fail to start:

1. Check Docker logs: `./scripts/dev_setup.sh logs`
2. Verify environment files exist and are properly configured
3. Ensure Docker has enough resources allocated
4. Check if required ports are available

## 📝 Additional Notes

- The development environment uses Django's built-in server for hot reloading
- The production environment uses Gunicorn with multiple workers
- Nginx serves static files and acts as a reverse proxy
- Database data is persisted using Docker volumes
- Static and media files are served through Nginx

## 🤝 Contributing

When contributing to this project:

1. Use the development environment for testing
2. Run migrations before committing changes
3. Test both development and production setups
4. Update this README if you add new features or scripts

## 📞 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review the logs using the log commands
3. Ensure all prerequisites are met
4. Verify environment configuration 