"""Tape library — list, read, and save capture metadata."""

import json
import os


def save_metadata(output_dir, base_name, metadata):
    path = os.path.join(output_dir, f"{base_name}.json")
    with open(path, "w") as f:
        json.dump(metadata, f, indent=2)


def list_tapes(output_dir, limit=None, offset=0, search=None):
    """List tapes with optional pagination and search.

    Args:
        output_dir: Directory containing tape metadata.
        limit: Maximum number of tapes to return (default: all).
        offset: Number of tapes to skip (for pagination).
        search: Optional search string to filter tapes by filename or tags.

    Returns:
        List of tape metadata dicts.
    """
    if not os.path.isdir(output_dir):
        return []
    tapes = []
    for fname in sorted(os.listdir(output_dir)):
        if fname.endswith(".json") and not fname.startswith("."):
            path = os.path.join(output_dir, fname)
            try:
                with open(path) as f:
                    meta = json.load(f)
                tapes.append(meta)
            except (json.JSONDecodeError, OSError):
                continue

    if search:
        search_lower = search.lower()
        filtered = []
        for t in tapes:
            filename = t.get("filename", "").lower()
            title = t.get("labels", {}).get("title", "").lower()
            tags = " ".join(t.get("labels", {}).get("tags", [])).lower()
            transcript = t.get("transcript", "").lower()
            if (search_lower in filename or search_lower in title or
                search_lower in tags or search_lower in transcript):
                filtered.append(t)
        tapes = filtered

    if offset > 0:
        tapes = tapes[offset:]
    if limit is not None:
        tapes = tapes[:limit]

    return tapes


def get_tape(output_dir, base_name):
    path = os.path.join(output_dir, f"{base_name}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def delete_tape(output_dir, base_name):
    """Delete a tape's video file and metadata.

    Returns:
        (success: bool, error: str|None)
    """
    json_path = os.path.join(output_dir, f"{base_name}.json")
    if not os.path.exists(json_path):
        return False, "Tape metadata not found"

    try:
        with open(json_path) as f:
            metadata = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False, "Could not read metadata"

    filename = metadata.get("filename")
    if filename:
        video_path = os.path.join(output_dir, filename)
        if os.path.exists(video_path):
            try:
                os.unlink(video_path)
            except OSError as e:
                return False, f"Could not delete video file: {e}"

    try:
        os.unlink(json_path)
    except OSError as e:
        return False, f"Could not delete metadata: {e}"

    return True, None


def export_library(output_dir, format="json"):
    """Export all tapes as JSON or CSV.

    Args:
        output_dir: Directory containing tape metadata.
        format: "json" or "csv"

    Returns:
        (success: bool, data: str|None, error: str|None)
    """
    tapes = list_tapes(output_dir)
    if not tapes:
        return True, "[]" if format == "json" else "", None

    if format == "json":
        return True, json.dumps(tapes, indent=2), None

    if format == "csv":
        if not tapes:
            return True, "", None
        import csv
        import io
        output = io.StringIO()
        fieldnames = ["filename", "duration_seconds", "size_bytes", "captured_at",
                      "validation.not_blank", "labels.title", "labels.tags", "transcript"]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for tape in tapes:
            row = {
                "filename": tape.get("filename", ""),
                "duration_seconds": tape.get("duration_seconds", 0),
                "size_bytes": tape.get("size_bytes", 0),
                "captured_at": tape.get("captured_at", ""),
                "validation.not_blank": tape.get("validation", {}).get("not_blank", False),
                "labels.title": tape.get("labels", {}).get("title", ""),
                "labels.tags": ",".join(tape.get("labels", {}).get("tags", [])),
                "transcript": (tape.get("transcript") or "")[:200],
            }
            writer.writerow(row)
        return True, output.getvalue(), None

    return False, None, f"Unknown format: {format}"
