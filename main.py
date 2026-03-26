#!/usr/bin/env python3
"""MemoryVault — VHS tape digitizer. Entry point."""

import sys
import os
import threading
import webbrowser
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}"


def run_server():
    from app import create_app
    app = create_app()
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)


def main():
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(1)

    webbrowser.open(URL)

    try:
        from tray import create_tray_icon
        icon = create_tray_icon()
        icon.run()
    except Exception:
        try:
            server_thread.join()
        except KeyboardInterrupt:
            pass

    print("MemoryVault shut down.")


if __name__ == "__main__":
    main()
