#!/bin/bash

# Function to find and kill processes by name
kill_processes() {
    local process_name="$1"
    local pids=($(pgrep "$process_name"))

    if [ ${#pids[@]} -eq 0 ]; then
        echo "No $process_name process found running."
    else
        echo "Killing $process_name process(es): ${pids[*]}"
        for pid in "${pids[@]}"; do
            kill "$pid"
        done
    fi
}

# Confirmation prompt function
confirm() {
    read -p "$1 [Y/n] " -n 1 -r
    echo    # move to a new line after user input
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        return 0  # true
    else
        return 1  # false
    fi
}

# List of process names to kill
process_names=("postgrest" "rclone")

# Construct a string listing the process names
process_names_list=$(printf ", %s" "${process_names[@]}")
process_names_list=${process_names_list:2}  # Remove the leading ", "

# Prompt user for confirmation before proceeding
if confirm "Are you sure you want to kill the following processes: $process_names_list?"; then
    # Loop through the list of process names and kill them
    for process_name in "${process_names[@]}"; do
        kill_processes "$process_name"
    done
else
    echo "Operation aborted."
fi