#!/bin/bash
POSTGREST_PID_FILE=$1

if [ -f "$POSTGREST_PID_FILE" ]; then
    kill "$(cat "$POSTGREST_PID_FILE")"
    if [ $? -eq 0 ]; then
        echo "postgREST process killed successfully"
        rm "$POSTGREST_PID_FILE"
    else
        echo "Failed to kill postgREST process"
    fi
else
    echo "$POSTGREST_PID_FILE not found, postgREST may not have been started"
fi