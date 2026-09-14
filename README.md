# watch_sync.sh

`watch_sync.sh` watches a local directory and synchronizes changes to a remote
directory with `rsync`.

*readme fully AI generated*

## Requirements

- Linux with `inotifywait` (`inotify-tools` package)
- `rsync`
- SSH access to the destination host

Install the tools on Debian or Ubuntu:

```sh
sudo apt install inotify-tools rsync openssh-client
```

## Basic usage

Make the script executable and run it with the source and destination paths:

```sh
chmod +x ./watch_sync.sh
./watch_sync.sh /path/to/local/dir user@server:/path/to/remote/dir
```

If the script uses configuration variables instead of arguments, edit the
values at the top of `watch_sync.sh` before starting it.

## Tutorial: add an rsync remote

1. Create an SSH key if needed:

	```sh
	ssh-keygen -t ed25519
	```

2. Install the key on the remote server:

	```sh
	ssh-copy-id user@server
	```

3. Test SSH and rsync:

	```sh
	ssh user@server
	rsync -av --dry-run ./local-dir/ user@server:/path/to/remote-dir/
	```

4. Use the same `user@server:/path/to/remote-dir` destination when starting
	`watch_sync.sh`.

The trailing slash on a source directory controls whether rsync copies the
directory itself or only its contents.

## Start automatically with systemd

Create a user service at `~/.config/systemd/user/watch-sync.service`:

```ini
[Unit]
Description=Watch and synchronize files
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/path/to/project
ExecStart=/path/to/project/watch_sync.sh /path/to/local/dir user@server:/path/to/remote/dir
Restart=on-failure

[Install]
WantedBy=default.target
```

Enable and start it:

```sh
systemctl --user daemon-reload
systemctl --user enable --now watch-sync.service
```

View logs and status with:

```sh
systemctl --user status watch-sync.service
journalctl --user -u watch-sync.service -f
```

To keep the service running after logout, enable lingering for your user:

```sh
loginctl enable-linger "$USER"
```
