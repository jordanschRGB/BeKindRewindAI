"""MemoryVault Doctor — diagnose setup issues and provide actionable guidance.

Run with: python -m engine.doctor
Or:      bekindrewind doctor

Checks:
- ffmpeg installation and version
- Video/audio device detection
- Disk space
- Configuration files
- Python dependencies
- AI model status (Whisper, llama.cpp)
"""

import os
import platform
import shutil
import sys


def run_diagnostics(verbose=False):
    """Run all diagnostic checks and return results.

    Returns:
        dict with check results and overall status
    """
    results = {
        "checks": [],
        "all_passed": True,
        "platform": platform.system(),
    }

    results["checks"].append(check_ffmpeg())
    results["checks"].append(check_devices())
    results["checks"].append(check_disk())
    results["checks"].append(check_config())
    results["checks"].append(check_dependencies())
    results["checks"].append(check_ai_models())

    results["all_passed"] = all(
        check["status"] == "ok" for check in results["checks"]
    )

    return results


def check_ffmpeg():
    """Check if ffmpeg is installed and working."""
    check = {"name": "ffmpeg", "status": "ok", "details": [], "fix": None}

    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")

    if not ffmpeg_path:
        check["status"] = "fail"
        check["details"].append("ffmpeg not found on PATH")
        check["fix"] = "Run: bekindrewind doctor --install-ffmpeg\nOr: brew install ffmpeg (macOS), apt install ffmpeg (Ubuntu)"
        return check

    check["details"].append(f"ffmpeg found at: {ffmpeg_path}")

    try:
        import subprocess
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            version_line = result.stdout.strip().split("\n")[0]
            check["details"].append(version_line)
        else:
            check["status"] = "warn"
            check["details"].append("ffmpeg found but returned non-zero exit code")
    except Exception as e:
        check["status"] = "warn"
        check["details"].append(f"Could not verify ffmpeg: {e}")

    if not ffprobe_path:
        check["status"] = "warn"
        check["details"].append("ffprobe not found - some validation features may not work")
        check["fix"] = "Install ffprobe from the same source as ffmpeg"
    else:
        check["details"].append(f"ffprobe found at: {ffprobe_path}")

    return check


def check_devices():
    """Check video and audio device detection."""
    check = {"name": "devices", "status": "ok", "details": [], "fix": None}

    try:
        from engine.devices import detect_video_devices, detect_audio_devices

        video_devices = detect_video_devices()
        audio_devices = detect_audio_devices()

        if not video_devices:
            check["status"] = "warn"
            check["details"].append("No video devices detected")
            check["fix"] = ("Check USB connections. On Linux: ls -la /dev/video*\n"
                          "On macOS: Check System Preferences > Security & Privacy")
        else:
            check["details"].append(f"Video devices: {len(video_devices)}")
            for label, _ in video_devices[:3]:
                check["details"].append(f"  - {label}")
            if len(video_devices) > 3:
                check["details"].append(f"  ... and {len(video_devices) - 3} more")

        if not audio_devices:
            check["status"] = "warn"
            check["details"].append("No audio devices detected")
            check["fix"] = "Check audio connections. On Linux: arecord -l"
        else:
            check["details"].append(f"Audio devices: {len(audio_devices)}")
            for label, _ in audio_devices[:3]:
                check["details"].append(f"  - {label}")
            if len(audio_devices) > 3:
                check["details"].append(f"  ... and {len(audio_devices) - 3} more")

    except Exception as e:
        check["status"] = "fail"
        check["details"].append(f"Device detection failed: {e}")
        check["fix"] = "Check that ffmpeg is properly installed"

    return check


def check_disk():
    """Check available disk space."""
    check = {"name": "disk_space", "status": "ok", "details": [], "fix": None}

    try:
        import shutil as sh
        disk = sh.disk_usage(os.path.expanduser("~"))
        free_gb = disk.free / (1024 ** 3)
        total_gb = disk.total / (1024 ** 3)
        used_pct = (disk.used / disk.total) * 100

        check["details"].append(f"Free: {free_gb:.1f} GB / {total_gb:.1f} GB ({used_pct:.1f}% used)")

        if free_gb < 1:
            check["status"] = "fail"
            check["details"].append("Very low disk space!")
            check["fix"] = "Free up disk space before recording. VHS captures need several GB per tape."
        elif free_gb < 5:
            check["status"] = "warn"
            check["details"].append("Low disk space - may run out during recording")
            check["fix"] = "Consider freeing up disk space. Each tape may need 2-4 GB."
    except Exception as e:
        check["status"] = "warn"
        check["details"].append(f"Could not check disk space: {e}")

    return check


def check_config():
    """Check if configuration file exists."""
    check = {"name": "configuration", "status": "ok", "details": [], "fix": None}

    config_dir = os.path.join(os.path.expanduser("~"), ".memoryvault")
    config_path = os.path.join(config_dir, "config.json")

    if not os.path.exists(config_path):
        check["status"] = "warn"
        check["details"].append("No configuration file found")
        check["fix"] = "Run the setup wizard at http://127.0.0.1:5000/setup"
        return check

    check["details"].append(f"Config file: {config_path}")

    try:
        import json
        with open(config_path) as f:
            config = json.load(f)

        if "video" in config and "audio" in config:
            check["details"].append("Configuration is valid")
        else:
            check["status"] = "warn"
            check["details"].append("Configuration is incomplete")
            check["fix"] = "Re-run the setup wizard at http://127.0.0.1:5000/setup"
    except Exception as e:
        check["status"] = "fail"
        check["details"].append(f"Config file is corrupted: {e}")
        check["fix"] = "Delete the config file and re-run setup: rm ~/.memoryvault/config.json"

    return check


def check_dependencies():
    """Check Python dependencies."""
    check = {"name": "python_deps", "status": "ok", "details": [], "fix": None}

    deps_status = "ok"
    missing_deps = []

    required = ["flask", "werkzeug"]
    optional = ["faster_whisper", "llama_cpp"]

    for dep in required:
        try:
            __import__(dep)
            check["details"].append(f"{dep}: installed")
        except ImportError:
            deps_status = "fail"
            missing_deps.append(dep)
            check["details"].append(f"{dep}: MISSING")
            check["fix"] = f"Install missing deps: pip install {' '.join(missing_deps)}"

    for dep in optional:
        try:
            __import__(dep)
            check["details"].append(f"{dep}: installed")
        except ImportError:
            check["details"].append(f"{dep}: not installed (optional)")
            if deps_status == "ok":
                deps_status = "warn"

    check["status"] = deps_status
    return check


def check_ai_models():
    """Check AI model status."""
    check = {"name": "ai_models", "status": "ok", "details": [], "fix": None}

    try:
        from engine.transcribe import is_whisper_available
        if is_whisper_available():
            check["details"].append("Whisper: available (auto-downloads model)")
        else:
            check["details"].append("Whisper: not available")
            check["status"] = "warn"
            check["fix"] = "Install faster-whisper: pip install faster-whisper"
    except Exception as e:
        check["details"].append(f"Whisper check failed: {e}")

    try:
        from engine.inference import get_download_status, ensure_llama_cpp
        llama_ok, llama_err = ensure_llama_cpp()
        if llama_ok:
            check["details"].append("llama.cpp: installed")
        else:
            check["details"].append(f"llama.cpp: not installed ({llama_err})")
            check["status"] = "warn"
            check["fix"] = "Install llama-cpp-python: pip install llama-cpp-python"

        model_status = get_download_status()
        for key, status in model_status.items():
            downloaded = "downloaded" if status.get("downloaded") else "not downloaded"
            check["details"].append(f"  {status['name']}: {downloaded}")
    except Exception as e:
        check["details"].append(f"AI model check failed: {e}")

    return check


def print_report(results):
    """Print a formatted diagnostic report."""
    print("\n" + "=" * 60)
    print("  MemoryVault Doctor")
    print("=" * 60)
    print(f"Platform: {results['platform']}")
    print()

    for check in results["checks"]:
        status_symbol = {"ok": "✓", "warn": "⚠", "fail": "✗"}.get(check["status"], "?")
        print(f"[{status_symbol}] {check['name'].upper()}: {check['status']}")

        for detail in check.get("details", []):
            print(f"    {detail}")

        if check.get("fix"):
            print(f"    → {check['fix']}")
        print()

    print("-" * 60)
    if results["all_passed"]:
        print("✓ All checks passed!")
    else:
        print("⚠ Some checks failed. Fix the issues above and run again.")
    print()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="MemoryVault Doctor - Diagnose setup issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--install-ffmpeg",
        action="store_true",
        help="Download and install ffmpeg if not found",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    if args.install_ffmpeg:
        print("Installing ffmpeg...")
        try:
            from engine.deps import download_ffmpeg
            success, err = download_ffmpeg()
            if success:
                print("✓ ffmpeg installed successfully!")
            else:
                print(f"✗ ffmpeg installation failed: {err}")
                sys.exit(1)
        except Exception as e:
            print(f"✗ ffmpeg installation failed: {e}")
            sys.exit(1)

    results = run_diagnostics(verbose=args.verbose)

    if args.json:
        import json
        print(json.dumps(results, indent=2))
    else:
        print_report(results)

    sys.exit(0 if results["all_passed"] else 1)


if __name__ == "__main__":
    main()
