# rclone sync watcher

`rclone_sync.py` watches `/home/phuid/Documents` for `.rnote` changes and
synchronizes them with `gdrive_vut:/Documents/` using `rclone bisync`.

## Requirements

- Linux with `inotifywait` (`inotify-tools` package)
- Python 3
- `rclone` configured with the `gdrive_vut` remote
- GTK 3 Python bindings for the optional tray icon

Install the tools on Debian or Ubuntu:

```sh
sudo apt install inotify-tools python3-gi
```

The tray icon uses AppIndicator when available. On desktops that provide it,
install the optional indicator bindings too:

```sh
sudo apt install gir1.2-appindicator3-0.1
```

## Basic usage

Run the watcher from a graphical terminal:

```sh
cd /path/to/rclone_sync
/usr/bin/python3 ./rclone_sync.py
```

The tray menu provides:

- **Sync now** to start a manual `rclone bisync`
- **View logs** to open `journalctl --user -u rclone_sync.service -f`
- **Quit** to stop the watcher

Use `--no-tray` when running without a graphical session:

```sh
/usr/bin/python3 ./rclone_sync.py --no-tray
```

## Start automatically with systemd

Create a user service at `~/.config/systemd/user/rclone_sync.service`:

```ini
[Unit]
Description=Watch and synchronize files
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/path/to/project
ExecStart=/usr/bin/python3 /path/to/rclone_sync/rclone_sync.py
Restart=on-failure

[Install]
WantedBy=default.target
```

Enable and start it:

```sh
systemctl --user daemon-reload
systemctl --user enable --now rclone_sync.service
```

View logs and status with the tray menu or:

```sh
systemctl --user status rclone_sync.service
journalctl --user -u rclone_sync.service -f
```

To keep the service running after logout, enable lingering for your user:

```sh
loginctl enable-linger "$USER"
```
