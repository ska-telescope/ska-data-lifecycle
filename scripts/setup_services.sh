#!/bin/bash
POSTGREST_PID_FILE=$1
RCLONE_PID_FILE=$2

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
# We only want to download if postgrest isn't already available AND an existing download isn't there
if ! command -v postgrest &> /dev/null && [[ ! -e "scripts/postgrest" ]]; then
    # Download and extract PostgREST binary release
    curl -sSL https://github.com/PostgREST/postgrest/releases/download/v12.0.2/postgrest-v12.0.2-linux-static-x64.tar.xz | tar xJf - -C scripts
fi


PATH="$(pwd)/scripts:$PATH" postgrest setup/postgREST/postgREST.conf &
echo "$!">$POSTGREST_PID_FILE

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

# We only want to download if unzip isn't available
if ! command -v unzip &> /dev/null; then
    apt-get update -qq
    apt-get install -y -qq unzip
fi

# Install r-clone for GitlabCI
echo "Installing rclone"
if [[ -n "$GITLAB_CI" ]]; then
    echo "Installing rclone"
    curl https://rclone.org/install.sh | bash
fi

rclone rcd --rc-serve --rc-no-auth >/dev/null 2>&1 &
echo "$!">$RCLONE_PID_FILE

attempt=1
while [[ $attempt -le $MAX_RETRIES ]]; do
    curl -s http://localhost:5572 > /dev/null
    if [[ $? -eq 0 ]]; then
        # successful connection
        break
    fi
    echo "Attempt $attempt failed for rclone server. Retrying in $DELAY_SECONDS second(s)..."
    sleep $DELAY_SECONDS
    ((attempt++))
done


if [[ $attempt -gt $MAX_RETRIES ]]; then
    echo "Max retries reached for rclone server. Unable to establish connection."
    exit 1
fi

