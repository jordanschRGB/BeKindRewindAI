"""JSON API blueprint for agent and programmatic access."""

import os
import shutil
from flask import Blueprint, jsonify, request, current_app

from session import Session, SessionState

api_bp = Blueprint("api", __name__)

_session = None


@api_bp.route("/status")
def status():
    config_dir = current_app.config["CONFIG_DIR"]
    output_dir = current_app.config["OUTPUT_DIR"]
    config_exists = os.path.exists(os.path.join(config_dir, "config.json"))
    disk = shutil.disk_usage(os.path.expanduser("~"))
    free_gb = disk.free / (1024 ** 3)
    from engine.deps import check_deps
    deps = check_deps()
    return jsonify({
        "status": "ok",
        "version": "0.1.0",
        "config_exists": config_exists,
        "session_active": _session is not None and _session.state.value not in ("done", "error"),
        "disk_free_gb": round(free_gb, 1),
        "deps": deps,
    })


@api_bp.route("/setup/detect", methods=["POST"])
def setup_detect():
    from engine.devices import detect_video_devices, detect_audio_devices, check_ffmpeg
    has_ffmpeg = check_ffmpeg()
    if not has_ffmpeg:
        return jsonify({"error": "ffmpeg not found", "code": "FFMPEG_NOT_FOUND"}), 500
    video = detect_video_devices()
    audio = detect_audio_devices()
    return jsonify({
        "video_devices": [{"label": l, "config": c} for l, c in video],
        "audio_devices": [{"label": l, "config": c} for l, c in audio],
    })


@api_bp.route("/setup/save", methods=["POST"])
def setup_save():
    import json as json_mod
    data = request.get_json()
    if not data or "video" not in data or "audio" not in data:
        return jsonify({"error": "video and audio config required", "code": "INVALID_CONFIG"}), 400
    config_dir = current_app.config["CONFIG_DIR"]
    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, "config.json")
    with open(config_path, "w") as f:
        json_mod.dump({"video": data["video"], "audio": data["audio"]}, f, indent=2)
    return jsonify({"status": "ok", "config_file": config_path})


@api_bp.route("/setup/test", methods=["POST"])
def setup_test():
    data = request.get_json()
    if not data or "video" not in data or "audio" not in data:
        return jsonify({"error": "video and audio config required", "code": "INVALID_CONFIG"}), 400
    from engine.devices import test_capture
    success, err = test_capture(data["video"], data["audio"])
    if success:
        return jsonify({"status": "ok"})
    else:
        return jsonify({"status": "error", "error": err, "code": "CAPTURE_TEST_FAILED"}), 400


@api_bp.route("/session/start", methods=["POST"])
def session_start():
    global _session
    data = request.get_json() or {}
    tape_count = data.get("tape_count", 1)
    names = data.get("names", [])
    output_dir = current_app.config["OUTPUT_DIR"]
    os.makedirs(output_dir, exist_ok=True)
    _session = Session(tape_count=tape_count, output_dir=output_dir, names=names)
    return jsonify(_session.to_dict())


@api_bp.route("/session/current")
def session_current():
    if _session is None:
        return jsonify({"error": "No active session", "code": "NO_SESSION"}), 404
    return jsonify(_session.to_dict())


@api_bp.route("/session/next", methods=["POST"])
def session_next():
    global _session
    if _session is None:
        return jsonify({"error": "No active session", "code": "NO_SESSION"}), 404
    if _session.state.value not in ("waiting",):
        return jsonify({"error": f"Cannot advance — state is {_session.state.value}", "code": "INVALID_STATE"}), 400
    import json as json_mod
    config_dir = current_app.config["CONFIG_DIR"]
    config_path = os.path.join(config_dir, "config.json")
    if not os.path.exists(config_path):
        return jsonify({"error": "No device config. Run setup first.", "code": "NO_CONFIG"}), 400
    with open(config_path) as f:
        config = json_mod.load(f)
    _session.advance()
    from pipeline import run_tape_pipeline
    run_tape_pipeline(_session, config)
    return jsonify(_session.to_dict())


@api_bp.route("/session/stop", methods=["POST"])
def session_stop():
    global _session
    if _session is None:
        return jsonify({"error": "No active session", "code": "NO_SESSION"}), 404
    from pipeline import stop_recording
    stop_recording(_session)
    return jsonify(_session.to_dict())


@api_bp.route("/library")
def library_list():
    from library import list_tapes
    output_dir = current_app.config["OUTPUT_DIR"]
    limit = request.args.get("limit", type=int)
    offset = request.args.get("offset", type=int, default=0)
    search = request.args.get("search", type=str, default=None)
    tapes = list_tapes(output_dir, limit=limit, offset=offset, search=search)
    return jsonify({"tapes": tapes, "offset": offset, "limit": limit})


@api_bp.route("/library/<tape_id>")
def library_get(tape_id):
    from library import get_tape
    output_dir = current_app.config["OUTPUT_DIR"]
    tape = get_tape(output_dir, tape_id)
    if tape is None:
        return jsonify({"error": "Tape not found", "code": "NOT_FOUND"}), 404
    return jsonify(tape)


@api_bp.route("/library/<tape_id>", methods=["DELETE"])
def library_delete(tape_id):
    from library import delete_tape
    output_dir = current_app.config["OUTPUT_DIR"]
    success, err = delete_tape(output_dir, tape_id)
    if not success:
        return jsonify({"error": err, "code": "DELETE_FAILED"}), 400
    return jsonify({"status": "ok", "deleted": tape_id})


@api_bp.route("/library/export")
def library_export():
    format_type = request.args.get("format", "json")
    if format_type not in ("json", "csv"):
        return jsonify({"error": "Format must be json or csv", "code": "INVALID_FORMAT"}), 400
    from library import export_library
    output_dir = current_app.config["OUTPUT_DIR"]
    success, data, err = export_library(output_dir, format_type)
    if not success:
        return jsonify({"error": err, "code": "EXPORT_FAILED"}), 500
    if format_type == "csv":
        return data, 200, {"Content-Type": "text/csv"}
    return data, 200, {"Content-Type": "application/json"}


@api_bp.route("/library/<tape_id>", methods=["PATCH"])
def library_update(tape_id):
    from library import get_tape
    output_dir = current_app.config["OUTPUT_DIR"]
    tape = get_tape(output_dir, tape_id)
    if tape is None:
        return jsonify({"error": "Tape not found", "code": "NOT_FOUND"}), 404

    data = request.get_json() or {}
    if "keep" in data:
        from cleanup import set_tape_keep
        success, err = set_tape_keep(output_dir, tape_id, bool(data["keep"]))
        if not success:
            return jsonify({"error": err, "code": "UPDATE_FAILED"}), 400

    return jsonify({"status": "ok", "updated": tape_id})


@api_bp.route("/storage")
def storage_stats():
    from cleanup import get_storage_stats
    output_dir = current_app.config["OUTPUT_DIR"]
    stats = get_storage_stats(output_dir)
    return jsonify(stats)


@api_bp.route("/cleanup", methods=["POST"])
def cleanup_run():
    from cleanup import cleanup_old_recordings
    output_dir = current_app.config["OUTPUT_DIR"]
    data = request.get_json() or {}
    days = data.get("days")
    if days is not None:
        days = int(days)
    dry_run = data.get("dry_run", True)
    result = cleanup_old_recordings(output_dir, days=days, dry_run=dry_run)
    return jsonify(result)


@api_bp.route("/cleanup/orphans", methods=["POST"])
def cleanup_orphans():
    from cleanup import cleanup_orphaned_temp_files
    output_dir = current_app.config["OUTPUT_DIR"]
    data = request.get_json() or {}
    dry_run = data.get("dry_run", True)
    result = cleanup_orphaned_temp_files(output_dir, dry_run=dry_run)
    return jsonify(result)


@api_bp.route("/settings/ai")
def ai_settings():
    from engine.inference import get_download_status, detect_hardware, ensure_llama_cpp
    from engine.transcribe import is_whisper_available
    llama_ok, llama_err = ensure_llama_cpp()
    return jsonify({
        "models": get_download_status(),
        "hardware": detect_hardware(),
        "whisper_installed": is_whisper_available(),
        "llama_cpp_installed": llama_ok,
        "llama_cpp_error": llama_err,
    })


@api_bp.route("/settings/ai/download/<model_key>", methods=["POST"])
def ai_download(model_key):
    from engine.inference import download_model
    success, err, path = download_model(model_key)
    if success:
        return jsonify({"status": "ok", "path": path})
    else:
        return jsonify({"status": "error", "error": err}), 400


@api_bp.route("/settings/ai/install-llama", methods=["POST"])
def ai_install_llama():
    from engine.inference import install_llama_cpp
    success, err = install_llama_cpp()
    if success:
        return jsonify({"status": "ok"})
    else:
        return jsonify({"status": "error", "error": err}), 500


@api_bp.route("/deps")
def deps_status():
    from engine.deps import check_deps
    return jsonify(check_deps())


@api_bp.route("/deps/install-ffmpeg", methods=["POST"])
def deps_install_ffmpeg():
    from engine.deps import download_ffmpeg, add_bin_to_path
    success, err = download_ffmpeg()
    if success:
        add_bin_to_path()
        return jsonify({"status": "ok"})
    else:
        return jsonify({"status": "error", "error": err}), 500


# ── Agent Chat ───────────────────────────────────────────────────────────────

_agent = None


@api_bp.route("/chat", methods=["POST"])
def chat():
    global _agent
    from agent import MemoryVaultAgent

    if _agent is None:
        _agent = MemoryVaultAgent()

    data = request.get_json() or {}
    message = data.get("message", "")

    if not message.strip():
        return jsonify({"error": "Empty message", "code": "EMPTY_MESSAGE"}), 400

    result = _agent.chat(message)
    result["whisper_prompt"] = _agent.get_whisper_prompt()
    return jsonify(result)


@api_bp.route("/chat/reset", methods=["POST"])
def chat_reset():
    global _agent
    _agent = None
    return jsonify({"status": "ok"})
