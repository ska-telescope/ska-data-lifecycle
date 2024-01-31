#!/bin/bash
POSTGREST_PID_FILE=$1

if ! command -v psql; then
    apt-get update -qq
    apt-get install -y -qq postgresql-client
fi

MAX_RETRIES=5
DELAY_SECONDS=1
attempt=1
while [[ $attempt -le $MAX_RETRIES ]]; do
    PGPASSWORD=mysecretpassword psql -U postgres -h localhost -p 5432 -f setup/DB/ska_dlm_meta.sql
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

# We only want to download if postgrest isn't already available AND an existing download isn't there
if ! command -v postgrest &> /dev/null && [[ ! -e "scripts/postgrest" ]]; then
    # Download and extract PostgREST binary release
    curl -sSL https://github.com/PostgREST/postgrest/releases/download/v12.0.2/postgrest-v12.0.2-linux-static-x64.tar.xz | tar xJf - -C scripts
fi

PATH="$(pwd)/scripts:$PATH" postgrest setup/postgREST/postgREST.conf &
echo "$!">$POSTGREST_PID_FILE
# Check if postgREST is running
# ps aux | grep postgrest
# Verify the port
# lsof -i :3001

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