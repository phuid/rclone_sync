#!/bin/bash

# Run the Python implementation directly so the parent process exits when Python exits.
exec /usr/bin/python3 "$(dirname "$0")/rclone_sync.py" "$@"
