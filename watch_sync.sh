#!/bin/bash

# Variables
LOCAL_DIR="/home/phuid/Documents"
REMOTE="gdrive_vut:/Documents/"
CHECK_DELAY=1

# Function to send desktop alerts
notify() {
	notify-send "Rclone Sync" "$1" --icon=drive-harddisk
}

log() {
	echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

notify "Watcher started for $LOCAL_DIR"

# Watch for events: modify, create, delete, move
inotifywait -m -r -e modify,create,delete,move "$LOCAL_DIR" |
	while read path action file; do
		if [[ "$file" =~ \.rnote$ ]]; then
			echo "Change detected in $file via $action. Waiting $CHECK_DELAY seconds..."
			log "Change detected in $file via $action. Waiting $CHECK_DELAY seconds..."

			# This 'sleep' prevents the sync from firing 50 times if
			# you save a large batch of files at once.
			sleep $CHECK_DELAY

			notify "Starting bisync..."
			log "Starting bisync..."
			if rclone bisync "$LOCAL_DIR" "$REMOTE"; then
				notify "Sync completed successfully!"
				log "Sync completed successfully!"
			else
				notify "Sync failed! Check logs."
				log "Sync failed! Check logs."
			fi
		else
			echo "Change detected in $file via $action, but it does not match the .rnote pattern. Ignoring."
			log "Change detected in $file via $action, but it does not match the .rnote pattern. Ignoring."
		fi
	done
