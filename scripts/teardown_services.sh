#!/bin/bash

POSTGREST_PID_FILE=$1
RCLONE_PID_FILE=$2

# Function to stop a process using its PID file
stop_process() {
    local pid_file="$1"
    local process_name="$2"

    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        rm "$pid_file" # removing the .pid file whether or not the process is killed
        kill "$pid"
        if [ $? -eq 0 ]; then
            echo "$process_name process killed successfully"
            return 0
        fi
        echo "Failed to kill $process_name process"
    else
        echo "$pid_file not found, $process_name may not have been started"
    fi
    echo "Could not find or kill $process_name. Try running: make kill-test-processes"
}

stop_process "$POSTGREST_PID_FILE" "postgREST"
stop_process "$RCLONE_PID_FILE" "rclone server"