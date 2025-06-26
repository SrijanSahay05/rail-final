# Quick Start Guide

## 🚀 Get Started in 3 Steps

### 1. Setup (First Time Only)
```bash
./scripts/dev_setup.sh
```

This will:
- Check Docker prerequisites
- Create `.env.dev` if needed
- Build and start all containers
- Set up the database

### 2. Daily Development
```bash
# Start development environment
./scripts/dev_setup.sh start

# View logs
./scripts/dev_setup.sh logs

# Stop when done
./scripts/dev_setup.sh stop
```

### 3. Access Your App
- **Main Application**: http://localhost
- **Django Admin**: http://localhost/admin
- **Direct Django**: http://localhost:8000

## 🛠️ Common Tasks

```bash
# Create superuser
./scripts/dev_setup.sh superuser

# Run migrations
./scripts/dev_setup.sh migrate

# Django shell
./scripts/dev_setup.sh shell

# Clean everything
./scripts/dev_setup.sh clean
```

## 🔧 Hot Reload Development

Thanks to volume mapping, your changes are instantly reflected:
- **Python files**: Auto-reload
- **Templates**: Instant update
- **Static files**: Run `collectstatic` or restart
- **Settings**: Restart container

## 📋 Available Commands

```bash
./scripts/dev_setup.sh [command]

Commands:
  (no args)      - Full setup (first time)
  start          - Start services
  stop           - Stop services  
  restart        - Restart services
  logs           - View logs
  shell          - Django shell
  superuser      - Create superuser
  migrate        - Run migrations
  collect-static - Collect static files
  clean          - Clean containers/volumes
```

## 🆘 Troubleshooting

### 502 Bad Gateway
```bash
# Check if web service is running
./scripts/dev_setup.sh logs

# Restart services
./scripts/dev_setup.sh restart
```

### Static Files Not Loading
```bash
# Collect static files
./scripts/dev_setup.sh collect-static
```

### Database Issues
```bash
# Clean start
./scripts/dev_setup.sh clean
./scripts/dev_setup.sh
```

