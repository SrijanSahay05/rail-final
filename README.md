# 🚀 HackStarter - Django Hackathon Template

A modern, development-ready Django starter template designed specifically for hackathons. Built with Tailwind CSS, dark/light mode, responsive design, and everything you need to focus on building your winning idea.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Django](https://img.shields.io/badge/django-5.2+-green.svg)
![Tailwind](https://img.shields.io/badge/tailwindcss-3.4+-blue.svg)
![Docker](https://img.shields.io/badge/docker-ready-blue.svg)

## ✨ Why HackStarter?

- **⚡ Lightning Fast Setup** - Clone and start coding in under 2 minutes
- **🎨 Beautiful UI** - Modern design with dark/light mode toggle
- **📱 Mobile First** - Responsive design that works on all devices
- **🔧 Developer Friendly** - Hot reload, easy customization, clean code structure
- **� Docker Containerized** - Consistent development environment
- **🏆 Hackathon Optimized** - Focus on your idea, not on setup

## 🎯 Perfect For

- Hackathons & Coding Competitions
- MVP Development
- Prototype Building
- Quick Project Launches
- Learning Django with Modern Stack

## ⚡ Quick Start

```bash
# Clone the template
git clone <your-repo-url> my-hackathon-project
cd my-hackathon-project

# One-command setup
./scripts/dev_setup.sh

# Start building! 🎉
open http://localhost
```

**That's it!** Your modern Django app is running with a beautiful UI, dark mode, and all the essentials.

## � What You Get

### 🖥️ Beautiful Frontend
- **Modern Design** - Clean, professional UI built with Tailwind CSS
- **Dark/Light Mode** - Automatic theme switching with user preference
- **Responsive Layout** - Perfect on desktop, tablet, and mobile
- **Smooth Animations** - Subtle transitions and hover effects
- **Accessibility Ready** - WCAG compliant with proper ARIA labels

### ⚙️ Powerful Backend
- **Django 5.2+** - Latest Django with all security updates
- **PostgreSQL 15** - Robust, scalable database
- **User Management** - Built-in authentication system ready to extend
- **Admin Panel** - Pre-configured Django admin
- **API Ready** - Easy to add REST APIs with Django REST Framework

### 🔧 Developer Experience
- **Hot Reload** - See changes instantly with Django development server
- **Docker Setup** - Consistent environment across all machines
- **Static Files** - Optimized asset serving with Nginx
- **Environment Config** - Easy configuration management with .env files
- **Helper Scripts** - Automated setup and common development tasks

### 🐳 Docker Environment
- **Multi-container Setup** - Django, PostgreSQL, Nginx all containerized
- **Volume Persistence** - Database and media files persist between restarts
- **Network Isolation** - Secure inter-service communication
- **Development Optimized** - Fast builds and instant code changes

## 📁 Project Structure

```
hackstarter-project/
├── 🎨 Frontend
│   ├── templates/           # Django HTML templates
│   │   ├── base.html       # Base template with navbar & theme toggle
│   │   └── core_home/      # Home page templates
│   └── static/             # Static assets
│       ├── css/styles.css  # Custom Tailwind CSS styles
│       └── images/         # Image assets
│
├── 🔧 Backend
│   ├── core/               # Main Django project
│   │   ├── settings.py     # Django configuration
│   │   ├── urls.py         # URL routing
│   │   └── wsgi.py         # WSGI configuration
│   ├── core_home/          # Home application
│   │   ├── models.py       # Database models
│   │   ├── views.py        # View logic
│   │   └── urls.py         # App URLs
│   ├── core_users/         # User management app
│   └── manage.py           # Django management script
│
├── 🐳 Docker Setup
│   ├── docker-compose.dev.yml  # Development orchestration
│   ├── dockerfile.dev          # Django container definition
│   ├── .env.dev               # Development environment variables
│   └── nginx/                 # Nginx configuration
│       └── nginx.dev.conf     # Development web server config
│
├── 🚀 Automation
│   └── scripts/               # Helper scripts
│       ├── dev_setup.sh       # Main development setup
│       ├── create_superuser.sh # Admin user creation
│       ├── make_migrations.sh  # Database migrations
│       └── flush_docker_database.sh # Database reset
│
└── 📚 Documentation
    ├── README.md              # This file
    ├── DEVELOPMENT.md         # Technical development guide
    └── QUICK_START.md         # Quick reference guide
```

## 🛠️ Development Commands

The project includes a comprehensive development script that handles all common tasks:

```bash
# Initial setup (run once)
./scripts/dev_setup.sh

# Daily development commands
./scripts/dev_setup.sh start    # Start all services
./scripts/dev_setup.sh stop     # Stop all services
./scripts/dev_setup.sh logs     # View container logs
./scripts/dev_setup.sh shell    # Open Django shell
./scripts/dev_setup.sh migrate  # Run database migrations
./scripts/dev_setup.sh superuser # Create admin user
./scripts/dev_setup.sh clean    # Clean up containers

# Direct access points
# Main app: http://localhost
# Admin: http://localhost/admin
# Django dev server: http://localhost:8000
```

## 🎛️ Customization Guide

### 1. Branding & Design
```bash
# Update brand name in templates/base.html
sed -i 's/HackStarter/YourAppName/g' templates/base.html

# Customize colors - modify Tailwind config in base.html
# Or add custom CSS in static/css/styles.css
```

### 2. Add New Django Apps
```bash
# Enter Django container
./scripts/dev_setup.sh shell

# Create new app
python manage.py startapp your_feature

# Add to INSTALLED_APPS in core/settings.py
```

### 3. Database Models
```python
# Add models to your app's models.py
class YourModel(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

# Create and apply migrations
./scripts/make_migrations.sh
./scripts/dev_setup.sh migrate
```

### 4. Environment Configuration
Edit `.env.dev` to customize:
```bash
# Django settings
DJANGO_SECRET_KEY=your-secret-key
DEBUG=True

# Database settings
POSTGRES_DB=your_db_name
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password

# Add API keys and external service credentials
```

## 🌐 Current Development Setup

This template is currently optimized for **development** with the following architecture:

- **Django Development Server** - Hot reload for rapid development
- **PostgreSQL Database** - Persistent data storage
- **Nginx Reverse Proxy** - Static file serving and routing
- **Docker Compose** - Multi-container orchestration
- **Volume Mapping** - Live code editing without rebuilds

## 📊 Performance & Features

- **⚡ Fast Development** - Hot reload with volume mounting
- **🔒 Secure Setup** - Environment variables for sensitive data
- **� Responsive Design** - Mobile-first Tailwind CSS framework
- **🌙 Theme Support** - Dark/light mode with localStorage persistence
- **🔍 Developer Tools** - Django admin, shell access, log viewing

## 📚 Documentation

- **📖 Quick Start**: [QUICK_START.md](QUICK_START.md) - Get running in 3 steps
- **🔧 Development Guide**: [DEVELOPMENT.md](DEVELOPMENT.md) - Technical setup and workflow
- **🐳 DevOps Documentation**: [DEVOPS.md](DEVOPS.md) - Docker architecture and automation
- **💡 API Reference**: Coming soon - REST API endpoints

## 🎯 Hackathon Success Tips

1. **Start with the Template** - Don't waste time on setup
2. **Focus on Your Idea** - Template handles the foundation
3. **Use the Components** - Pre-built UI components save hours
4. **Deploy Early** - Use provided deployment scripts
5. **Demo Ready** - Beautiful UI impresses judges

## 🤝 Contributing

We welcome contributions! See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup and guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Django](https://djangoproject.com/)
- Styled with [Tailwind CSS](https://tailwindcss.com/)
- Icons from [Heroicons](https://heroicons.com/)
- Fonts from [Google Fonts](https://fonts.google.com/)

## 📞 Support

- 📖 **Documentation**: Check out our [Development Guide](DEVELOPMENT.md)
- 🐛 **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/your-repo/discussions)
- 📧 **Email**: support@hackstarter.dev

---

**⭐ Star this repo if it helped you win a hackathon!**

Built with ❤️ for the hackathon community
