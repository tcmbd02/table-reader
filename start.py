"""Start Table Reader: run the app on this PC and open it in the browser. This is what the desktop shortcut runs.

In the packaged app there is no console window (nothing for staff to close by mistake): the page's Quit button stops
the app, and starting it again while it runs just opens the page again. Problems are written to
<Documents>\\Table Reader\\table-reader.log for the support person.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

import uvicorn

import jobs
from app import create_app

HOST = "127.0.0.1"
PORTS = range(8765, 8785)


def _is_table_reader(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/ping", timeout=3) as r:
            return json.load(r).get("app") == "table-reader"
    except (OSError, ValueError):
        return False


def _port_free(port: int) -> bool:
    """Binding answers at once; *connecting* to a closed port takes about 2 seconds each on Windows."""
    with socket.socket() as s:
        try:
            s.bind((HOST, port))
        except OSError:
            return False
        return True


def _setup_logging() -> None:
    try:
        folder = jobs.default_root().parent
        folder.mkdir(parents=True, exist_ok=True)
        level = logging.INFO if os.environ.get("TABLE_READER_DEBUG") else logging.WARNING
        logging.basicConfig(filename=folder / "table-reader.log", level=level, encoding="utf-8",
                            format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    except OSError:
        pass                                           # no log file is better than no app


def main() -> int:
    _setup_logging()
    logging.info("start: imports done")
    port = None
    for candidate in PORTS:
        if _port_free(candidate):
            port = candidate
            break
        if _is_table_reader(candidate):                 # already running: just show it again
            webbrowser.open(f"http://localhost:{candidate}/")
            return 0
    if port is None:
        logging.error("No free port in %s", PORTS)
        print("Table Reader could not start: no free port. Restart the computer and try again.")
        return 1
    logging.info("start: port %s chosen, creating app", port)
    # log_config=None: a packaged app without a console has no stdout/stderr for uvicorn's own logging to write to
    server = uvicorn.Server(uvicorn.Config(create_app(), host=HOST, port=port, log_level="warning", log_config=None))
    server.config.app.state.on_quit = lambda: setattr(server, "should_exit", True)
    server.config.app.state.inbox.start()       # files saved into the Inbox folder are read by themselves
    threading.Thread(target=lambda: (time.sleep(1.0), webbrowser.open(f"http://localhost:{port}/")), daemon=True).start()
    logging.info("start: serving")
    print(f"Table Reader is running at http://localhost:{port}/ - use Quit in the page, or close this window, to stop it.")
    server.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
