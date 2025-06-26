echo "Flush Docker Database"
echo "====================="

docker-compose -f docker-compose.dev.yml exec web python manage.py flush --no-input

echo "[✅] database flushed"

