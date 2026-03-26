"""Tape library — list, read, and save capture metadata."""

import json
import os


def save_metadata(output_dir, base_name, metadata):
    path = os.path.join(output_dir, f"{base_name}.json")
    with open(path, "w") as f:
        json.dump(metadata, f, indent=2)


def list_tapes(output_dir):
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
