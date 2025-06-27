#!/usr/bin/env python3
"""
Script to set up Google OAuth2 application for Django-Allauth
"""
import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/app')

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp

def setup_google_oauth():
    # Get or create the site
    site, created = Site.objects.get_or_create(
        pk=1,
        defaults={
            'domain': 'srijansahay05.in',
            'name': 'srijansahay05.in'
        }
    )
    
    if created:
        print(f"Created site: {site.domain}")
    else:
        print(f"Site already exists: {site.domain}")
        # Update the existing site
        site.domain = 'srijansahay05.in'
        site.name = 'srijansahay05.in'
        site.save()
        print(f"Updated site: {site.domain}")
    
    # Get Google OAuth credentials from environment
    client_id = os.environ.get('GOOGLE_OAUTH2_CLIENT_ID', 'your-client-id')
    client_secret = os.environ.get('GOOGLE_OAUTH2_CLIENT_SECRET', 'your-client-secret')
    
    if client_id == 'your-client-id' or client_secret == 'your-client-secret':
        print("WARNING: Google OAuth2 credentials are not properly set in environment variables!")
        print("Please update GOOGLE_OAUTH2_CLIENT_ID and GOOGLE_OAUTH2_CLIENT_SECRET in .env.prod")
    
    # Create or update Google social app
    google_app, created = SocialApp.objects.get_or_create(
        provider='google',
        defaults={
            'name': 'Google OAuth2',
            'client_id': client_id,
            'secret': client_secret,
        }
    )
    
    if created:
        print(f"Created Google OAuth2 app")
    else:
        print(f"Google OAuth2 app already exists, updating...")
        google_app.client_id = client_id
        google_app.secret = client_secret
        google_app.save()
    
    # Add the site to the social app
    google_app.sites.add(site)
    print(f"Added site {site.domain} to Google OAuth2 app")
    
    print("\nGoogle OAuth2 setup completed!")
    print(f"Site: {site.domain}")
    print(f"Google App: {google_app.name}")
    print(f"Client ID: {google_app.client_id[:10]}...")

if __name__ == '__main__':
    setup_google_oauth()
