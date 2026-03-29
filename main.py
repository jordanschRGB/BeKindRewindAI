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
    import argparse

    parser = argparse.ArgumentParser(
        description="MemoryVault - VHS tape digitizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage="%(prog)s [options]",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose debug logging",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run diagnostic checks and exit",
    )
    parser.add_argument(
        "--install-ffmpeg",
        action="store_true",
        help="Download and install ffmpeg if not found",
    )

    args, _ = parser.parse_known_args()

    if args.verbose:
        from engine.logging_ import set_verbose
        set_verbose(True)

    if args.doctor:
        from engine.doctor import main as doctor_main
        sys.argv = ["doctor"]
        if args.verbose:
            sys.argv.append("-v")
        if args.install_ffmpeg:
            sys.argv.append("--install-ffmpeg")
        doctor_main()
        return

    if args.install_ffmpeg:
        print("Installing ffmpeg...")
        try:
            from engine.deps import download_ffmpeg
            success, err = download_ffmpeg()
            if success:
                print("ffmpeg installed successfully!")
            else:
                print(f"ffmpeg installation failed: {err}")
                sys.exit(1)
        except Exception as e:
            print(f"ffmpeg installation failed: {e}")
            sys.exit(1)
        return

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
