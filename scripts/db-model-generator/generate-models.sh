#!/bin/bash
#
# Set file and destination path
DLM_MODELS_FILE=dlm_models.py
DLM_MODELS_DIR=../../src/ska_dlm/dlm_db

# Start the PostgreSQL container with your schema
echo docker compose up
docker-compose up -d

# Wait for DB to initialise
echo Waiting 10 seconds for DB to initisalise
sleep 10

# Install sqlacodegen in a temporary container (or use host python if preferred)
echo generate ORM class models
docker run --rm \
  -v "$PWD":/app \
  --network="host" \
  python:3.12-slim bash -c "
    pip install sqlacodegen psycopg2-binary &&
    sqlacodegen postgresql+psycopg2://user:pass@localhost:5433/tempdb > /app/$DLM_MODELS_FILE
  "

# Stop the container when done
echo docker compose down
docker-compose down --volumes

echo show diff between generated and current models file....
diff $DLM_MODELS_FILE $DLM_MODELS_DIR/$DLM_MODELS_FILE
echo waiting 5 seconds in case user wants to break out before copying over destingation file
sleep 5
mv -f $DLM_MODELS_FILE $DLM_MODELS_DIR/$DLM_MODELS_FILE

echo "✅ $DLM_MODELS_FILE generated from create-enum-types.sql and create-tables.sql"


