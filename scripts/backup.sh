#!/bin/sh
set -e
docker compose exec db pg_dump -U commodity commodity_agent > "backup_$(date +%Y%m%d_%H%M%S).sql"
echo "Backup created"
