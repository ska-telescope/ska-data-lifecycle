#!/bin/sh
set -eu

key_dir=${1:?key directory is required}
private_key="$key_dir/id_rsa"
public_key="$private_key.pub"

mkdir -p "$key_dir"
if [ -s "$private_key" ] && [ -s "$public_key" ]; then
    exit 0
fi

if [ -e "$private_key" ] || [ -e "$public_key" ]; then
    echo "Incomplete SSH key pair in $key_dir" >&2
    exit 1
fi

ssh-keygen -q -t rsa -b 4096 -N '' -f "$private_key"
if [ ! -s "$private_key" ] || [ ! -s "$public_key" ]; then
    echo "ssh-keygen did not create a complete key pair in $key_dir" >&2
    exit 1
fi

chmod 600 "$private_key"
chmod 644 "$public_key"
