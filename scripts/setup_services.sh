#!/bin/bash
POSTGREST_PID_FILE=$1

if ! command -v psql &> /dev/null; then
    apt-get update -qq
    apt-get install -y -qq postgresql-client
fi

MAX_RETRIES=5
DELAY_SECONDS=1
attempt=1
while [[ $attempt -le $MAX_RETRIES ]]; do
    PGPASSWORD=mysecretpassword psql -U postgres -h localhost -p 5432 -f setup/DB/ska_dlm_meta.sql > /dev/null
    if [[ $? -eq 0 ]]; then
    # successful connection
        break
    fi
    echo "Attempt $attempt failed for postgres. Retrying in $DELAY_SECONDS second(s)..."
    sleep $DELAY_SECONDS
    ((attempt++))
done

if [[ $attempt -gt $MAX_RETRIES ]]; then
    echo "Max retries reached for postgres. Unable to establish connection."
    exit 1
fi


# postgrest setup/postgREST/postgREST.conf &> /dev/null &
postgrest setup/postgREST/postgREST.conf &> postgrest.log &
echo "$!">$POSTGREST_PID_FILE
# Check if postgREST is running
ps aux | grep postgrest
# Verify the port
netstat -tuln | grep 3001

attempt=1
while [[ $attempt -le $MAX_RETRIES ]]; do
    curl -s http://localhost:3001 > /dev/null
    if [[ $? -eq 0 ]]; then
    # successful connection
        break
    fi
    echo "Attempt $attempt failed for postgREST. Retrying in $DELAY_SECONDS second(s)..."
    sleep $DELAY_SECONDS
    ((attempt++))
done

if [[ $attempt -gt $MAX_RETRIES ]]; then
    echo "Max retries reached for postgREST. Unable to establish connection."
    exit 1
fi