#!/usr/bin/python3

import argparse
import os
import re
import signal
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime

LOCAL_DIR = "/home/phuid/Documents"
REMOTE = "gdrive_vut:/Documents/"
CHECK_DELAY = 1
WATCH_EVENTS = "close_write,create,delete,move,modify,attrib"


try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, GLib
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3
    AppIndicator3_available = True
except Exception:
    AppIndicator3_available = False
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
    except Exception:
        Gtk = None
        GLib = None
    else:
        AppIndicator3 = None


def log(message: str) -> None:
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} - {message}", flush=True)


class TrayIcon:
    def __init__(self, on_sync, on_logs):
        self.icon = None
        self.indicator = None
        self.enabled = False
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            return
        if Gtk is None:
            return

        try:
            if AppIndicator3_available and AppIndicator3 is not None:
                self.indicator = AppIndicator3.Indicator.new(
                    "rclone-sync",
                    "emblem-default",
                    AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
                )
                self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
                self.indicator.set_attention_icon("dialog-error")
                self.indicator.set_menu(self.create_menu(on_sync, on_logs))
                self.enabled = True
                self.set_state("idle")
                return

            log("AppIndicator3 is unavailable; using legacy Gtk.StatusIcon fallback.")
            self.icon = Gtk.StatusIcon()
            self.icon.set_title("Rclone Sync")
            self.icon.set_visible(True)
            self.icon.connect("popup-menu", self.show_menu, on_sync, on_logs)
            self.set_state("idle")
            self.enabled = True
        except Exception as exc:
            log(f"Tray icon unavailable: {exc}")
            self.icon = None
            self.indicator = None
            self.enabled = False

    def create_menu(self, on_sync, on_logs):
        menu = Gtk.Menu()

        sync_item = Gtk.MenuItem(label="Sync now")
        sync_item.connect("activate", lambda _item: on_sync())
        menu.append(sync_item)

        logs_item = Gtk.MenuItem(label="View logs")
        logs_item.connect("activate", lambda _item: on_logs())
        menu.append(logs_item)

        menu.append(Gtk.SeparatorMenuItem())
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda _item: self.quit())
        menu.append(quit_item)
        menu.show_all()
        return menu

    def show_menu(self, _icon, button, activate_time, on_sync, on_logs):
        menu = self.create_menu(on_sync, on_logs)
        menu.popup(None, None, Gtk.StatusIcon.position_menu, self.icon, button, activate_time)

    def set_state(self, state: str) -> None:
        if GLib is not None and threading.current_thread() is not threading.main_thread():
            GLib.idle_add(self.set_state, state)
            return

        icon_names = {
            "idle": "emblem-default",
            "syncing": "view-refresh",
            "error": "dialog-error",
            "stopped": "media-playback-stop",
        }

        if self.indicator is not None:
            try:
                icon_name = icon_names.get(state, "emblem-default")
                self.indicator.set_icon_full(icon_name, f"Rclone Sync: {state}")
            except Exception:
                self.enabled = False
            return

        if not self.enabled or self.icon is None:
            return
        try:
            self.icon.set_from_icon_name(icon_names.get(state, "emblem-default"))
            self.icon.set_tooltip_text(f"Rclone Sync: {state}")
        except Exception:
            self.enabled = False

    def quit(self) -> None:
        if self.indicator is not None:
            try:
                self.indicator.set_status(AppIndicator3.IndicatorStatus.PASSIVE)
            except Exception:
                pass
        if self.icon is not None:
            try:
                self.icon.set_visible(False)
            except Exception:
                pass
        if Gtk is not None:
            try:
                Gtk.main_quit()
            except Exception:
                pass

    def run(self) -> None:
        if self.enabled:
            Gtk.main()


class SyncController:
    def __init__(self, tray: TrayIcon):
        self.tray = tray
        self.sync_lock = threading.Lock()
        self.running = True
        self.sync_timer = None
        self.inotify_proc = None
        self.last_trigger = 0.0

    def set_state(self, state: str) -> None:
        if self.tray is not None:
            self.tray.set_state(state)

    def sync_once(self, origin: str = "automatic") -> None:
        if not self.sync_lock.acquire(blocking=False):
            log(f"Sync request ignored; another sync is already running (origin={origin}).")
            return

        started_at = time.monotonic()
        self.set_state("syncing")
        log(f"Sync started (origin={origin}, local={LOCAL_DIR}, remote={REMOTE}).")
        try:
            completed = subprocess.run(
                ["rclone", "bisync", LOCAL_DIR, REMOTE],
                check=False,
            )
        except FileNotFoundError:
            log(f"Sync failed after {time.monotonic() - started_at:.1f}s: rclone not found in PATH.")
            self.set_state("error")
        else:
            duration = time.monotonic() - started_at
            if completed.returncode == 0:
                log(f"Sync completed successfully in {duration:.1f}s (origin={origin}).")
                self.set_state("idle")
            else:
                log(f"Sync failed with exit code {completed.returncode} after {duration:.1f}s (origin={origin}).")
                self.set_state("error")
        finally:
            self.sync_lock.release()
            log(f"Sync finished (origin={origin}).")

    def request_sync(self) -> None:
        log("Manual sync requested from tray menu.")
        sync_thread = threading.Thread(target=self.sync_once, args=("manual",), daemon=True)
        sync_thread.start()

    def view_logs(self) -> None:
        journal_args = ["journalctl", "--user", "-u", "rclone_sync.service", "-f"]
        terminal_commands = [
            ["x-terminal-emulator", "-e", *journal_args],
            ["gnome-terminal", "--", *journal_args],
            ["konsole", "-e", *journal_args],
            ["xfce4-terminal", "-e", " ".join(journal_args)],
        ]

        for command in terminal_commands:
            if shutil.which(command[0]):
                try:
                    subprocess.Popen(command)
                    return
                except OSError:
                    continue
        log("Could not find a terminal emulator to open journalctl.")

    def schedule_sync(self) -> None:
        if self.sync_timer is not None:
            self.sync_timer.cancel()
            log("Pending automatic sync rescheduled after another file event.")

        log(f"Automatic sync scheduled in {CHECK_DELAY}s.")
        self.sync_timer = threading.Timer(
            CHECK_DELAY,
            lambda: self.sync_once("file change"),
        )
        self.sync_timer.daemon = True
        self.sync_timer.start()

    def handle_inotify_line(self, line: str) -> None:
        stripped = line.strip()
        if not stripped:
            return

        try:
            full_path, event = stripped.rsplit(maxsplit=1)
        except ValueError:
            return

        event_name = event.strip().split(",", 1)[0].upper()
        if not full_path or not event_name:
            return
        if not re.search(r"\.rnote$", full_path, flags=re.IGNORECASE):
            log(f"Ignoring non-.rnote event: {full_path} ({event_name}).")
            return
        if event_name not in {"CREATE", "DELETE", "MOVE", "MODIFY", "CLOSE_WRITE", "ATTRIB"}:
            log(f"Ignoring unsupported event: {full_path} ({event_name}).")
            return

        now = time.time()
        if now - self.last_trigger < 0.5:
            return
        self.last_trigger = now

        log(f"Change detected in {full_path} via {event_name}. Waiting {CHECK_DELAY} seconds...")
        self.schedule_sync()

    def watch_directory(self) -> None:
        try:
            self.inotify_proc = subprocess.Popen(
                [
                    "inotifywait",
                    "-m",
                    "-r",
                    "-e",
                    WATCH_EVENTS,
                    "--format",
                    "%w%f %e",
                    LOCAL_DIR,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            log("inotifywait is not installed or not in PATH.")
            return

        log(f"Filesystem watcher active for {LOCAL_DIR} (events={WATCH_EVENTS}).")

        if self.inotify_proc.stdout is None:
            return

        for raw_line in self.inotify_proc.stdout:
            if not self.running:
                break
            self.handle_inotify_line(raw_line)

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        if self.sync_timer is not None:
            self.sync_timer.cancel()
            log("Pending automatic sync cancelled.")
        if self.inotify_proc is not None and self.inotify_proc.poll() is None:
            self.inotify_proc.terminate()
            log("Filesystem watcher stopped.")
        self.set_state("stopped")


def install_signal_handlers(controller: SyncController, tray: TrayIcon) -> None:
    def _shutdown(signum, frame):
        controller.stop()
        if tray is not None:
            tray.quit()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Watch a local folder and sync it with rclone bisync.")
    parser.add_argument("--no-tray", action="store_true", help="Disable the GTK tray icon even when a graphical session is available.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    controller = SyncController(None)
    tray = None if args.no_tray else TrayIcon(controller.request_sync, controller.view_logs)
    if tray is not None and not tray.enabled:
        tray = None
    controller.tray = tray
    install_signal_handlers(controller, tray)

    log(f"Watcher started for {LOCAL_DIR}")
    watcher = threading.Thread(target=controller.watch_directory, daemon=True)
    watcher.start()

    log("Initial sync queued.")
    initial_sync = threading.Thread(target=controller.sync_once, args=("initial",), daemon=True)
    initial_sync.start()

    try:
        if tray is not None:
            tray.run()
        else:
            while controller.running:
                time.sleep(0.2)
    except SystemExit:
        pass
    finally:
        controller.stop()
        if tray is not None:
            tray.quit()

    return 0


if __name__ == "__main__":
    sys.exit(main())
