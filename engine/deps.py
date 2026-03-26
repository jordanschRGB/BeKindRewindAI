"""Dependency management — ensure ffmpeg and other tools are available."""

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile

SYSTEM = platform.system()
APP_DIR = os.path.join(os.path.expanduser("~"), ".memoryvault")
BIN_DIR = os.path.join(APP_DIR, "bin")

# ffmpeg download URLs (essentials builds)
FFMPEG_URLS = {
    "Windows": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
    "Darwin": "https://evermeet.cx/ffmpeg/getrelease/zip",
    "Linux": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
}


def find_ffmpeg():
    """Check if ffmpeg is available. Returns path or None."""
    # Check our bundled location first
    bundled = os.path.join(BIN_DIR, "ffmpeg.exe" if SYSTEM == "Windows" else "ffmpeg")
    if os.path.exists(bundled):
        return bundled

    # Check system PATH
    path = shutil.which("ffmpeg")
    if path:
        return path

    return None


def find_ffprobe():
    """Check if ffprobe is available. Returns path or None."""
    bundled = os.path.join(BIN_DIR, "ffprobe.exe" if SYSTEM == "Windows" else "ffprobe")
    if os.path.exists(bundled):
        return bundled

    path = shutil.which("ffprobe")
    if path:
        return path

    return None


def check_deps():
    """Check all dependencies. Returns dict of status."""
    ffmpeg_path = find_ffmpeg()
    ffprobe_path = find_ffprobe()

    result = {
        "ffmpeg": {
            "installed": ffmpeg_path is not None,
            "path": ffmpeg_path,
        },
        "ffprobe": {
            "installed": ffprobe_path is not None,
            "path": ffprobe_path,
        },
        "all_ok": ffmpeg_path is not None and ffprobe_path is not None,
    }

    # Get version if installed
    if ffmpeg_path:
        try:
            r = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, timeout=10)
            first_line = r.stdout.strip().split("\n")[0] if r.stdout else ""
            result["ffmpeg"]["version"] = first_line
        except Exception:
            result["ffmpeg"]["version"] = "unknown"

    return result


def download_ffmpeg(progress_callback=None):
    """Download ffmpeg to ~/.memoryvault/bin/.

    Args:
        progress_callback: Optional callable(bytes_downloaded, total_bytes)

    Returns:
        (success: bool, error: str|None)
    """
    import urllib.request

    url = FFMPEG_URLS.get(SYSTEM)
    if not url:
        return False, f"No ffmpeg download available for {SYSTEM}"

    os.makedirs(BIN_DIR, exist_ok=True)

    try:
        if SYSTEM == "Windows":
            return _download_ffmpeg_windows(url, progress_callback)
        elif SYSTEM == "Darwin":
            return _download_ffmpeg_mac(url, progress_callback)
        else:
            return _download_ffmpeg_linux(url, progress_callback)
    except Exception as e:
        return False, str(e)


def _download_ffmpeg_windows(url, progress_callback):
    """Download and extract ffmpeg for Windows."""
    import urllib.request

    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()

    try:
        def _report(block_num, block_size, total_size):
            if progress_callback:
                progress_callback(block_num * block_size, total_size)

        urllib.request.urlretrieve(url, tmp.name, reporthook=_report)

        # Extract ffmpeg.exe and ffprobe.exe from the zip
        with zipfile.ZipFile(tmp.name, "r") as zf:
            for name in zf.namelist():
                basename = os.path.basename(name)
                if basename in ("ffmpeg.exe", "ffprobe.exe"):
                    # Extract to BIN_DIR with flat name
                    target = os.path.join(BIN_DIR, basename)
                    with zf.open(name) as src, open(target, "wb") as dst:
                        dst.write(src.read())

        # Verify
        ffmpeg_path = os.path.join(BIN_DIR, "ffmpeg.exe")
        if os.path.exists(ffmpeg_path):
            return True, None
        else:
            return False, "ffmpeg.exe not found in downloaded archive"
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _download_ffmpeg_mac(url, progress_callback):
    """Download ffmpeg for macOS."""
    import urllib.request

    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()

    try:
        def _report(block_num, block_size, total_size):
            if progress_callback:
                progress_callback(block_num * block_size, total_size)

        urllib.request.urlretrieve(url, tmp.name, reporthook=_report)

        with zipfile.ZipFile(tmp.name, "r") as zf:
            for name in zf.namelist():
                basename = os.path.basename(name)
                if basename in ("ffmpeg", "ffprobe"):
                    target = os.path.join(BIN_DIR, basename)
                    with zf.open(name) as src, open(target, "wb") as dst:
                        dst.write(src.read())
                    os.chmod(target, 0o755)

        if os.path.exists(os.path.join(BIN_DIR, "ffmpeg")):
            return True, None
        else:
            return False, "ffmpeg not found in downloaded archive"
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _download_ffmpeg_linux(url, progress_callback):
    """Download ffmpeg for Linux."""
    import urllib.request
    import tarfile

    tmp = tempfile.NamedTemporaryFile(suffix=".tar.xz", delete=False)
    tmp.close()

    try:
        def _report(block_num, block_size, total_size):
            if progress_callback:
                progress_callback(block_num * block_size, total_size)

        urllib.request.urlretrieve(url, tmp.name, reporthook=_report)

        with tarfile.open(tmp.name, "r:xz") as tf:
            for member in tf.getmembers():
                basename = os.path.basename(member.name)
                if basename in ("ffmpeg", "ffprobe"):
                    member.name = basename
                    tf.extract(member, BIN_DIR)
                    os.chmod(os.path.join(BIN_DIR, basename), 0o755)

        if os.path.exists(os.path.join(BIN_DIR, "ffmpeg")):
            return True, None
        else:
            return False, "ffmpeg not found in downloaded archive"
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def add_bin_to_path():
    """Add ~/.memoryvault/bin/ to PATH so subprocess calls find our ffmpeg."""
    if BIN_DIR not in os.environ.get("PATH", ""):
        os.environ["PATH"] = BIN_DIR + os.pathsep + os.environ.get("PATH", "")
