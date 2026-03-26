"""Smart labeling — generate title, description, tags from transcript + video frames.

Supports multiple backends:
1. HTTP API (LM Studio, Ollama, OpenRouter — any OpenAI-compatible endpoint)
2. Local llama-cpp-python (bundled fallback for offline use)
"""

import json
import os
import subprocess
import tempfile
import urllib.request
import urllib.error

# Default inference endpoint — configurable in settings
# Set to None to use local llama-cpp-python only
DEFAULT_API_URL = None  # e.g. "http://100.96.5.85:6942/v1/chat/completions"
DEFAULT_MODEL = "qwen3.5-4b"

# Config file for user settings
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".memoryvault")
CONFIG_FILE = os.path.join(CONFIG_DIR, "ai_config.json")

SYSTEM_PROMPT = "You analyze VHS tape recordings and generate metadata. Always respond with valid JSON only, no markdown, no explanation."

USER_PROMPT_TEMPLATE = """You are analyzing a digitized VHS tape recording. Based on the content below, generate a short title, a one-sentence description, and 3-5 relevant tags.

Respond in this exact JSON format:
{{"title": "...", "description": "...", "tags": ["...", "..."]}}

Audio transcript:
{transcript}

JSON response:"""


def load_ai_config():
    """Load AI config (endpoint, model, API key)."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_ai_config(config):
    """Save AI config."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_api_url():
    """Get configured API URL, or None for local-only."""
    config = load_ai_config()
    return config.get("api_url", DEFAULT_API_URL)


def get_api_key():
    """Get configured API key (for OpenRouter etc)."""
    config = load_ai_config()
    return config.get("api_key", "")


def get_model_name():
    """Get configured model name."""
    config = load_ai_config()
    return config.get("model", DEFAULT_MODEL)


def _call_api(messages, api_url=None, api_key=None, model=None):
    """Call an OpenAI-compatible chat completions endpoint.

    Returns:
        (success: bool, response_text: str|None, error: str|None)
    """
    url = api_url or get_api_url()
    key = api_key or get_api_key()
    model_name = model or get_model_name()

    if not url:
        return False, None, "No API endpoint configured"

    payload = json.dumps({
        "model": model_name,
        "messages": messages,
        "max_tokens": 512,
        "temperature": 0.3,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
    }
    if key:
        headers["Authorization"] = f"Bearer {key}"

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["choices"][0]["message"]["content"]
            return True, text, None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        return False, None, f"API error {e.code}: {body}"
    except urllib.error.URLError as e:
        return False, None, f"Connection failed: {e.reason}"
    except Exception as e:
        return False, None, f"API call failed: {e}"


def _call_local(messages):
    """Call local llama-cpp-python as fallback.

    Returns:
        (success: bool, response_text: str|None, error: str|None)
    """
    try:
        from engine.inference import LlamaInference, get_model_path, is_model_downloaded
    except ImportError:
        return False, None, "inference engine not available"

    if not is_model_downloaded("qwen-labeler"):
        return False, None, "Qwen model not downloaded and no API endpoint configured"

    try:
        model_path = get_model_path("qwen-labeler")
        model = LlamaInference(model_path, n_ctx=4096)
        response = model.chat(messages, max_tokens=256, temperature=0.3)
        model.unload()
        return True, response, None
    except Exception as e:
        return False, None, f"Local inference failed: {e}"


def _call_llm(messages):
    """Try API first, fall back to local.

    Returns:
        (success: bool, response_text: str|None, error: str|None)
    """
    # Try HTTP API first
    api_url = get_api_url()
    if api_url:
        success, text, err = _call_api(messages)
        if success:
            return True, text, None
        # API failed — fall through to local

    # Try local llama-cpp-python
    return _call_local(messages)


def sample_frames(video_path, count=4, output_dir=None):
    """Extract evenly-spaced frames from a video.

    Returns:
        (success: bool, frame_paths: list[str], error: str|None)
    """
    if not os.path.exists(video_path):
        return False, [], f"Video not found: {video_path}"

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="memoryvault_frames_")

    probe_cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "json", video_path,
    ]
    try:
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        duration = float(json.loads(result.stdout)["format"]["duration"])
    except Exception:
        duration = 60

    frames = []
    for i in range(count):
        timestamp = (duration / (count + 1)) * (i + 1)
        frame_path = os.path.join(output_dir, f"frame_{i:02d}.jpg")

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(timestamp),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            frame_path,
        ]

        try:
            subprocess.run(cmd, capture_output=True, timeout=30)
            if os.path.exists(frame_path) and os.path.getsize(frame_path) > 0:
                frames.append(frame_path)
        except (subprocess.TimeoutExpired, OSError):
            continue

    if not frames:
        return False, [], "Could not extract any frames"

    return True, frames, None


def generate_labels(transcript=None, frame_paths=None):
    """Generate title, description, and tags from transcript.

    Returns:
        (success: bool, labels: dict|None, error: str|None)
    """
    if not transcript and not frame_paths:
        return False, None, "Need at least a transcript or video frames"

    # Build prompt — Qwen 3.5 4B handles 262K+ context, no need to truncate
    transcript_text = (transcript or "").strip()
    if not transcript_text:
        transcript_text = "(No speech detected in recording)"

    prompt = USER_PROMPT_TEMPLATE.format(transcript=transcript_text)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    # Call LLM (API first, local fallback)
    success, response, err = _call_llm(messages)
    if not success:
        return False, None, err

    # Parse JSON from response
    labels = _parse_labels(response)
    if labels:
        return True, labels, None
    else:
        return False, None, f"Could not parse labels from response: {response[:200]}"


def _parse_labels(text):
    """Try to extract JSON labels from model output."""
    text = text.strip()

    # Remove markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    try:
        data = json.loads(text)
        if "title" in data and "tags" in data:
            return {
                "title": str(data.get("title", "")),
                "description": str(data.get("description", "")),
                "tags": [str(t) for t in data.get("tags", [])],
            }
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end])
            if "title" in data:
                return {
                    "title": str(data.get("title", "")),
                    "description": str(data.get("description", "")),
                    "tags": [str(t) for t in data.get("tags", [])],
                }
        except json.JSONDecodeError:
            pass

    return None


def label_video(video_path, transcript=None):
    """Full pipeline: sample frames + generate labels.

    Returns:
        (success: bool, labels: dict|None, error: str|None)
    """
    frame_paths = []

    success, frames, _ = sample_frames(video_path)
    if success:
        frame_paths = frames

    try:
        return generate_labels(transcript=transcript, frame_paths=frame_paths)
    finally:
        for fp in frame_paths:
            try:
                os.unlink(fp)
            except OSError:
                pass
