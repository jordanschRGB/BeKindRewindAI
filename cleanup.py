"""Storage cleanup — age-based deletion, orphaned temp cleanup, disk monitoring."""

import glob
import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timedelta


VAULT_DIR = os.path.join(os.path.expanduser("~"), "Videos", "MemoryVault")
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".memoryvault")
DEFAULT_RETENTION_DAYS = 30
DISK_WARNING_THRESHOLD_GB = 5


def get_storage_stats(output_dir=None):
    """Get storage usage statistics.

    Returns:
        dict with disk_free_gb, disk_used_gb, tape_count, total_size_bytes,
        oldest_tape, newest_tape, orphaned_temp_dirs, orphaned_temp_files
    """
    if output_dir is None:
        output_dir = VAULT_DIR

    stats = {
        "disk_free_gb": 0,
        "disk_used_gb": 0,
        "tape_count": 0,
        "total_size_bytes": 0,
        "oldest_tape": None,
        "newest_tape": None,
        "orphaned_temp_dirs": [],
        "orphaned_temp_files": [],
        "disk_warning": False,
    }

    home = os.path.expanduser("~")
    disk = shutil.disk_usage(home)
    stats["disk_free_gb"] = round(disk.free / (1024 ** 3), 2)
    stats["disk_used_gb"] = round(disk.used / (1024 ** 3), 2)
    stats["disk_warning"] = stats["disk_free_gb"] < DISK_WARNING_THRESHOLD_GB

    if not os.path.isdir(output_dir):
        return stats

    json_files = []
    video_files = []
    for fname in os.listdir(output_dir):
        fpath = os.path.join(output_dir, fname)
        if fname.endswith(".json") and not fname.startswith("."):
            json_files.append((fname, fpath))
        elif fname.endswith((".mp4", ".mkv")) and not fname.startswith("."):
            video_files.append((fname, fpath))

    stats["tape_count"] = len(json_files)

    for fname, fpath in json_files:
        try:
            with open(fpath) as f:
                meta = json.load(f)
            size = meta.get("size_bytes", 0)
            stats["total_size_bytes"] += size
            captured = meta.get("captured_at", "")
            if captured:
                if stats["oldest_tape"] is None or captured < stats["oldest_tape"]:
                    stats["oldest_tape"] = captured
                if stats["newest_tape"] is None or captured > stats["newest_tape"]:
                    stats["newest_tape"] = captured
        except (json.JSONDecodeError, OSError):
            pass

    stats["orphaned_temp_dirs"] = _find_orphaned_frame_dirs()
    stats["orphaned_temp_files"] = _find_orphaned_temp_files(output_dir)

    return stats


def _find_orphaned_frame_dirs():
    """Find orphaned memoryvault_frames_* directories in /tmp."""
    orphaned = []
    tmp = tempfile.gettempdir()
    pattern = os.path.join(tmp, "memoryvault_frames_*")
    for d in glob.glob(pattern):
        if os.path.isdir(d):
            orphaned.append(d)
    return orphaned


def _find_orphaned_temp_files(output_dir):
    """Find temp .wav and .mkv files in output_dir that aren't associated with running processes."""
    orphaned = []
    if not os.path.isdir(output_dir):
        return orphaned

    for fname in os.listdir(output_dir):
        if fname.endswith(("_raw.mkv", ".wav")) and not os.path.basename(fname).startswith("."):
            fpath = os.path.join(output_dir, fname)
            age_days = (time.time() - os.path.getmtime(fpath)) / 86400
            if age_days > 1:
                orphaned.append(fpath)
    return orphaned


def cleanup_old_recordings(output_dir=None, days=None, dry_run=True, remove_raw=False):
    """Delete recordings older than specified days.

    Args:
        output_dir: Directory containing recordings
        days: Delete recordings older than this many days (default: 30)
        dry_run: If True, return what would be deleted without deleting
        remove_raw: If True, also delete raw .mkv files

    Returns:
        dict with deleted_count, freed_bytes, errors, protected_tapes
    """
    if output_dir is None:
        output_dir = VAULT_DIR
    if days is None:
        days = DEFAULT_RETENTION_DAYS

    cutoff = datetime.now() - timedelta(days=days)
    result = {
        "deleted_count": 0,
        "freed_bytes": 0,
        "errors": [],
        "protected_tapes": [],
        "dry_run": dry_run,
    }

    if not os.path.isdir(output_dir):
        return result

    for fname in os.listdir(output_dir):
        if not fname.endswith(".json") or fname.startswith("."):
            continue

        fpath = os.path.join(output_dir, fname)
        try:
            with open(fpath) as f:
                meta = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        captured_str = meta.get("captured_at", "")
        if not captured_str:
            continue

        try:
            captured = datetime.fromisoformat(captured_str.replace("Z", "+00:00").split("+")[0])
        except (ValueError, AttributeError):
            try:
                captured = datetime.fromisoformat(captured_str)
            except ValueError:
                continue

        if captured >= cutoff:
            continue

        if meta.get("keep", False):
            result["protected_tapes"].append(meta.get("base_name", fname))
            continue

        base_name = fname[:-5]
        video_extensions = [".mp4", ".mkv"]
        if remove_raw:
            video_extensions.append("_raw.mkv")

        deleted_bytes = 0
        for ext in video_extensions:
            vpath = os.path.join(output_dir, base_name + ext)
            if os.path.exists(vpath):
                try:
                    size = os.path.getsize(vpath)
                    if not dry_run:
                        os.unlink(vpath)
                    deleted_bytes += size
                except OSError as e:
                    result["errors"].append(f"Failed to delete {vpath}: {e}")

        try:
            json_size = os.path.getsize(fpath)
            if not dry_run:
                os.unlink(fpath)
            result["deleted_count"] += 1
            result["freed_bytes"] += deleted_bytes + json_size
        except OSError as e:
            result["errors"].append(f"Failed to delete {fpath}: {e}")

    return result


def cleanup_orphaned_temp_files(output_dir=None, dry_run=True):
    """Remove orphaned temporary directories and files from crashed sessions.

    Args:
        output_dir: Directory to scan for temp files
        dry_run: If True, return what would be deleted without deleting

    Returns:
        dict with deleted_dirs, deleted_files, errors
    """
    if output_dir is None:
        output_dir = VAULT_DIR

    result = {
        "deleted_dirs": 0,
        "deleted_files": 0,
        "freed_bytes": 0,
        "errors": [],
        "dry_run": dry_run,
    }

    orphaned_dirs = _find_orphaned_frame_dirs()
    for d in orphaned_dirs:
        try:
            if not dry_run:
                shutil.rmtree(d)
            result["deleted_dirs"] += 1
        except OSError as e:
            result["errors"].append(f"Failed to remove {d}: {e}")

    orphaned_files = _find_orphaned_temp_files(output_dir)
    for f in orphaned_files:
        try:
            size = os.path.getsize(f)
            if not dry_run:
                os.unlink(f)
            result["deleted_files"] += 1
            result["freed_bytes"] += size
        except OSError as e:
            result["errors"].append(f"Failed to remove {f}: {e}")

    return result


def set_tape_keep(output_dir, base_name, keep=True):
    """Set or unset the keep flag on a tape to protect it from auto-cleanup.

    Returns:
        (success: bool, error: str|None)
    """
    json_path = os.path.join(output_dir, f"{base_name}.json")
    if not os.path.exists(json_path):
        return False, "Tape not found"

    try:
        with open(json_path) as f:
            metadata = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return False, f"Could not read metadata: {e}"

    metadata["keep"] = keep

    try:
        with open(json_path, "w") as f:
            json.dump(metadata, f, indent=2)
        return True, None
    except OSError as e:
        return False, f"Could not write metadata: {e}"


def get_tape_keep_status(output_dir, base_name):
    """Check if a tape is marked as keep-protected."""
    json_path = os.path.join(output_dir, f"{base_name}.json")
    if not os.path.exists(json_path):
        return None
    try:
        with open(json_path) as f:
            meta = json.load(f)
        return meta.get("keep", False)
    except (json.JSONDecodeError, OSError):
        return None