#!/bin/bash
POSTGREST_PID_FILE=$1
RCLONE_PID_FILE=$2

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

if [ -f "$RCLONE_PID_FILE" ]; then
    kill "$(cat "$RCLONE_PID_FILE")"
    if [ $? -eq 0 ]; then
        echo "rclone server process killed successfully"
        rm "$RCLONE_PID_FILE"
    else
        echo "Failed to kill rclone server process"
    fi
else
    echo "$RCLONE_PID_FILE not found, rclone server may not have been started"
fi