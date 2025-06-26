#!/bin/bash

echo "Creating Migrations in Production Docker Container"
echo "================================================="
echo ""

# Define the local apps that need migrations
LOCAL_APPS=(
    "core_home"
    "core_users"
    "feature_railways"
    "feature_transaction"
)

echo "🔧 Making migrations for each app individually..."
echo ""

# Create migrations for each local app
for app in "${LOCAL_APPS[@]}"; do
    echo "📝 Creating migrations for: $app"
    docker-compose -f docker-compose.dev.yml exec web python manage.py makemigrations $app
    if [ $? -eq 0 ]; then
        echo "✅ Migrations created successfully for $app"
    else
        echo "❌ Failed to create migrations for $app"
    fi
    echo ""
done

echo "📝 Creating migrations for any remaining apps..."
docker-compose -f docker-compose.dev.yml exec web python manage.py makemigrations
if [ $? -eq 0 ]; then
    echo "✅ General makemigrations completed"
else
    echo "❌ General makemigrations failed"
fi
echo ""

echo "🚀 Applying all migrations..."
echo ""

# Apply migrations for core_users first (since other apps depend on it)
echo "📦 Applying core_users migrations first..."
docker-compose -f docker-compose.dev.yml exec web python manage.py migrate core_users
if [ $? -eq 0 ]; then
    echo "✅ core_users migrations applied successfully"
else
    echo "❌ Failed to apply core_users migrations"
fi
echo ""

# Apply all remaining migrations
echo "📦 Applying all remaining migrations..."
docker-compose -f docker-compose.dev.yml exec web python manage.py migrate
if [ $? -eq 0 ]; then
    echo "✅ All migrations applied successfully"
else
    echo "❌ Failed to apply migrations"
fi
echo ""

echo "🎉 Migration process completed!"
echo "=============================================="
