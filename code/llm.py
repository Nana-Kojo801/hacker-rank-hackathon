"""Minimal OpenAI chat client with on-disk caching and token accounting (no third-party deps)."""
import hashlib
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path

def _load_dotenv():
    """Populate os.environ from an uncommitted .env at the repo root (never overrides real variables)."""
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()
CACHE_DIR = Path(__file__).parent / ".cache" / "llm"
USAGE_FILE = Path(__file__).parent / ".cache" / "usage.jsonl"
API_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1") + "/chat/completions"
DEFAULT_MODEL = os.environ.get("AUDIT_MODEL", "gpt-4o-mini")


def available():
    return bool(os.environ.get("OPENAI_API_KEY"))


def chat_json(system, user, model=None, purpose="", schema_hint=None, max_retries=3):
    """Call the model asking for a JSON object. Returns parsed dict; results are cached by prompt hash."""
    model = model or DEFAULT_MODEL
    key = hashlib.sha256(json.dumps([model, system, user], ensure_ascii=False).encode()).hexdigest()
    cache = CACHE_DIR / f"{key}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))["result"]
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode(), method="POST", headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]})
    last = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read())
            break
        except (urllib.error.URLError, TimeoutError) as e:     # retry transient failures
            last = e
            time.sleep(2 ** attempt)
    else:
        raise RuntimeError(f"OpenAI call failed: {last}")
    result = json.loads(data["choices"][0]["message"]["content"])
    usage = data.get("usage", {})
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"result": result, "usage": usage, "model": model}), encoding="utf-8")
    with USAGE_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"model": model, "purpose": purpose, "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0)}) + "\n")
    return result


def chat_vision(prompt, image_path, model=None, purpose="vision_transcribe", max_retries=3):
    """Transcribe an image to text with a vision-capable model (cached, usage logged)."""
    import base64
    model = model or os.environ.get("AUDIT_VISION_MODEL", DEFAULT_MODEL)
    raw = Path(image_path).read_bytes()
    key = hashlib.sha256(model.encode() + prompt.encode() + raw).hexdigest()
    cache = CACHE_DIR / f"{key}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))["result"]
    b64 = base64.b64encode(raw).decode()
    body = {"model": model, "temperature": 0, "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}]}
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode(), method="POST", headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]})
    last = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read())
            break
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(2 ** attempt)
    else:
        raise RuntimeError(f"OpenAI vision call failed: {last}")
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"result": text, "usage": usage, "model": model}), encoding="utf-8")
    with USAGE_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"model": model, "purpose": purpose, "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0)}) + "\n")
    return text
