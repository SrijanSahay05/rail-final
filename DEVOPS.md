# 🐳 DevOps Documentation - HackStarter

This document explains the containerized development setup, why specific choices were made, and how the Docker infrastructure supports rapid hackathon development.

## 🎯 Philosophy & Goals

The HackStarter template is designed with these principles:

1. **Zero-friction Setup** - One command gets you running
2. **Development Speed** - Hot reload, instant feedback
3. **Consistency** - Same environment across all machines
4. **Simplicity** - Easy to understand and modify
5. **Hackathon-ready** - Focus on building, not configuring

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Development Environment            │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │    Nginx    │    │   Django    │    │ PostgreSQL  │     │
│  │   (Port 80) │    │ (Port 8000) │    │ (Port 5432) │     │
│  │             │────│             │────│             │     │
│  │ Static Files│    │   Web App   │    │  Database   │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                                             │
│  Volumes:                                                   │
│  • Source Code (Live Reload)                               │
│  • Database Data (Persistent)                              │
│  • Static Files (Nginx Serving)                            │
│  • Media Files (User Uploads)                              │
└─────────────────────────────────────────────────────────────┘
```

## 🔧 Container Breakdown

### 1. Django Web Container (`web`)

**Purpose**: Runs the Django development server with hot reload capability.

```dockerfile
# dockerfile.dev
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

**Key Features**:
- **Hot Reload**: Volume-mounted source code enables instant code changes
- **Development Server**: Django's built-in server with debug capabilities
- **Environment Variables**: Configuration via `.env.dev` file
- **Port Mapping**: Internal 8000 → External 8000 for direct access

**Volume Mounts**:
```yaml
volumes:
  - .:/app                    # Live code editing
  - static_volume:/app/staticfiles  # Static file collection
  - media_volume:/app/media   # User uploaded files
```

**Why This Setup**:
- **Fast Iteration**: No container rebuilds needed for code changes
- **Debug Friendly**: Full Django debug toolbar and error pages
- **Easy Access**: Direct port access for development tools

### 2. PostgreSQL Database Container (`db`)

**Purpose**: Provides a robust, persistent database for development.

```yaml
db:
  image: postgres:15
  env_file: .env.dev
  volumes:
    - postgres_data:/var/lib/postgresql/data
  ports:
    - "5432:5432"
```

**Key Features**:
- **PostgreSQL 15**: Latest stable version with performance improvements
- **Data Persistence**: Named volume ensures data survives container restarts
- **Port Exposure**: Direct database access for debugging and admin tools
- **Environment Configuration**: Database credentials via `.env.dev`

**Why PostgreSQL**:
- **Production Parity**: Same database in dev and production
- **Robust Features**: JSON fields, full-text search, advanced indexing
- **Hackathon Ready**: Handle complex data relationships out of the box

### 3. Nginx Web Server Container (`nginx`)

**Purpose**: Handles static file serving and acts as reverse proxy.

```nginx
# nginx/nginx.dev.conf
upstream django {
    server web:8000;
}

server {
    listen 80;
    
    # Static files - served directly by Nginx
    location /static/ {
        alias /app/staticfiles/;
    }
    
    # Media files - user uploads
    location /media/ {
        alias /app/media/;
    }
    
    # All other requests - proxy to Django
    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Key Features**:
- **Static File Optimization**: Nginx serves CSS, JS, images efficiently
- **Reverse Proxy**: Routes dynamic requests to Django
- **Single Entry Point**: All traffic through port 80
- **Development Optimized**: Simple configuration, easy debugging

**Why Nginx**:
- **Performance**: Much faster static file serving than Django
- **Production Similarity**: Same setup as production deployment
- **Single Port**: Simplified access via http://localhost

## 🔄 Development Workflow

### Container Startup Sequence

```bash
./scripts/dev_setup.sh
```

1. **Environment Check**: Verifies Docker is running
2. **Environment Setup**: Creates `.env.dev` if missing
3. **Database Initialization**: Starts PostgreSQL container
4. **Django Preparation**: 
   - Collects static files
   - Creates database migrations
   - Applies migrations
   - Starts development server
5. **Nginx Launch**: Starts reverse proxy
6. **Health Check**: Verifies all services are running

### Live Development Process

```mermaid
graph LR
    A[Code Change] --> B[File Watch]
    B --> C[Django Reload]
    C --> D[Instant Update]
    D --> E[Browser Refresh]
```

**What Happens**:
1. Developer edits Python code
2. Docker volume reflects change instantly
3. Django dev server detects change
4. Server reloads automatically
5. Browser shows updated content

### Database Development

```bash
# Access Django shell
./scripts/dev_setup.sh shell

# Create migrations
./scripts/make_migrations.sh

# Apply migrations
./scripts/dev_setup.sh migrate

# Access database directly
docker-compose -f docker-compose.dev.yml exec db psql -U postgres_user -d django_dev
```

## 📁 File Structure & Volumes

### Volume Strategy

```yaml
volumes:
  # Named volumes (persistent)
  postgres_data:      # Database files
  static_volume:      # Collected static files
  media_volume:       # User uploads
  
  # Bind mounts (live editing)
  .:/app             # Source code
```

**Why This Approach**:
- **Live Editing**: Code changes reflect immediately
- **Data Persistence**: Database survives container restarts
- **Performance**: Named volumes are faster than bind mounts for data
- **Separation**: Code and data have different lifecycle needs

### Environment Configuration

```bash
# .env.dev structure
DJANGO_SECRET_KEY=dev-secret-key
DEBUG=True
POSTGRES_DB=django_dev
POSTGRES_USER=postgres_user
POSTGRES_PASSWORD=postgres_password
DB_HOST=db
DB_PORT=5432
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,web,nginx
```

**Security Considerations**:
- Development keys (not production-ready)
- Permissive hosts for development
- Debug mode enabled for detailed errors
- Easy to override for different environments

## 🚀 Automation Scripts

### `dev_setup.sh` - Master Script

**Purpose**: Single command for complete environment setup.

```bash
#!/bin/bash
# Key functions:
check_docker()           # Verify Docker is running
check_docker_compose()   # Verify docker-compose available
create_env_file()        # Generate .env.dev if missing
setup_development()      # Build and start containers
run_migrations()         # Set up database schema
```

**Why This Approach**:
- **Beginner Friendly**: One command gets everything running
- **Error Handling**: Checks prerequisites before starting
- **Idempotent**: Safe to run multiple times
- **Educational**: Shows what's happening at each step

### Helper Scripts

```bash
scripts/
├── create_superuser.sh      # Django admin user creation
├── make_migrations.sh       # Database schema changes
└── flush_docker_database.sh # Reset database
```

**Design Philosophy**:
- **Single Purpose**: Each script does one thing well
- **Safe Operations**: Confirmation prompts for destructive actions
- **Development Focus**: Optimized for rapid iteration

## 🔍 Debugging & Monitoring

### Container Health Monitoring

```bash
# Check all services
docker-compose -f docker-compose.dev.yml ps

# View logs
./scripts/dev_setup.sh logs

# Individual service logs
docker-compose -f docker-compose.dev.yml logs web
docker-compose -f docker-compose.dev.yml logs db
docker-compose -f docker-compose.dev.yml logs nginx
```

### Common Debugging Scenarios

**Database Connection Issues**:
```bash
# Check database container
docker-compose -f docker-compose.dev.yml logs db

# Test connection
docker-compose -f docker-compose.dev.yml exec web python manage.py dbshell
```

**Static Files Not Loading**:
```bash
# Recollect static files
docker-compose -f docker-compose.dev.yml exec web python manage.py collectstatic

# Check Nginx configuration
docker-compose -f docker-compose.dev.yml logs nginx
```

**Permission Issues**:
```bash
# Fix volume permissions
docker-compose -f docker-compose.dev.yml exec web chown -R $(id -u):$(id -g) /app
```

## 🎯 Hackathon Optimization

### Rapid Development Features

1. **Instant Feedback Loop**:
   - Hot reload for Python code
   - Live CSS/JS updates
   - No build delays

2. **Pre-configured Stack**:
   - Django admin for data management
   - PostgreSQL for complex queries
   - Tailwind for rapid UI development

3. **Easy Customization**:
   - Environment variables for configuration
   - Modular Django apps
   - Docker for consistent deployment

### Performance Considerations

**Development Speed**:
- Volume mounts for instant code changes
- Development server with debug info
- Simplified Nginx configuration

**Resource Usage**:
- Lightweight base images
- Shared volumes between containers
- Minimal container overhead

## 🔮 Future Considerations

### Potential Enhancements

1. **Redis Integration**: For caching and session storage
2. **Celery Workers**: For background task processing
3. **Development Tools**: Django Debug Toolbar, django-extensions
4. **Testing Setup**: Automated testing containers
5. **Production Pipeline**: CI/CD integration ready

### Scalability Path

The current setup provides a clear path to production:

```
Development → Staging → Production
     ↓           ↓          ↓
  Hot Reload → Gunicorn → Load Balancer
  SQLite/PG → PostgreSQL → Multi-DB
  Django Dev → Nginx/SSL → CDN/Caching
```

## 📚 Learning Resources

### Docker Concepts Used

- **Multi-stage builds**: Different images for dev/prod
- **Volume mounts**: Live code editing
- **Environment variables**: Configuration management
- **Container networking**: Service communication
- **Health checks**: Service monitoring

### Django Patterns Implemented

- **Project structure**: Modular app organization
- **Settings management**: Environment-based configuration
- **Static files**: Nginx serving optimization
- **Database migrations**: Schema version control
- **Admin interface**: Rapid data management

---

This DevOps setup prioritizes developer experience and rapid iteration while maintaining a clear path to production deployment. The containerized approach ensures consistency across development environments and provides a solid foundation for hackathon projects that need to scale quickly.
