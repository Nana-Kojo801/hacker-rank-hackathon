"""Build the explainer video: narration (ElevenLabs) -> timing -> rendered scenes (Playwright) -> MP4s + captions.

    python3 video/src/build.py tts        # synthesise (cached) narration for every chapter
    python3 video/src/build.py render     # render chapter_XX.mp4 from cached narration
    python3 video/src/build.py full       # captions.srt + full.mp4 (captions burned in)
    python3 video/src/build.py frames     # one QA frame per scene into video/build/frames
    python3 video/src/build.py all

The API key is read from ELEVENLABS_API_KEY and never printed.  Narration MP3s and their character
alignment are cached in video/cache/, keyed by a hash of voice, model, settings and text, so a re-run
spends no credits.
"""
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from chapters import CHAPTERS  # noqa: E402

SRC = Path(__file__).resolve().parent
VIDEO = SRC.parent
CACHE = VIDEO / "cache"
BUILD = VIDEO / "build"

VOICE_ID = "Xb7hH8MSUJpSbSDYk0k2"          # "Alice - Clear, Engaging Educator" (premade)
VOICE_NAME = "Alice"
MODEL_ID = "eleven_multilingual_v2"
SETTINGS = {"stability": 0.55, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True}
RATE = 44100
LEAD = 2.6          # seconds of chapter title card before the narration starts
PAD = 0.45          # silence inserted at every scene boundary
TAIL = 1.4          # hold after the last word
FPS = 30
CUE = re.compile(r"\[(\d+)\]")


# ----------------------------------------------------------------------------- text
def chapter_text(ch):
    """Return (plain text, [scene start index], [{cue_no: char index}] per scene)."""
    parts, starts, cues, pos = [], [], [], 0
    for _, raw in ch["scenes"]:
        if parts:
            parts.append(" ")
            pos += 1
        starts.append(pos)
        sc, plain, last = {}, [], 0
        for m in CUE.finditer(raw):
            plain.append(raw[last:m.start()])
            sc[int(m.group(1))] = pos + len("".join(plain))
            last = m.end()
        plain.append(raw[last:])
        text = "".join(plain)
        parts.append(text)
        cues.append(sc)
        pos += len(text)
    return "".join(parts), starts, cues


# ----------------------------------------------------------------------------- tts
def cache_paths(n, text):
    key = hashlib.sha256(json.dumps([VOICE_ID, MODEL_ID, SETTINGS, text]).encode()).hexdigest()[:12]
    return CACHE / f"chapter_{n:02d}_{key}.mp3", CACHE / f"chapter_{n:02d}_{key}.json"


def tts(n, ch):
    text, _, _ = chapter_text(ch)
    mp3, js = cache_paths(n, text)
    if mp3.exists() and js.exists():
        return mp3, js, 0
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ELEVENLABS_API_KEY is not set")
    url = (f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/with-timestamps"
           f"?output_format=mp3_44100_128")
    body = json.dumps({"text": text, "model_id": MODEL_ID, "voice_settings": SETTINGS}).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"xi-api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.load(r)
    CACHE.mkdir(parents=True, exist_ok=True)
    mp3.write_bytes(base64.b64decode(d["audio_base64"]))
    js.write_text(json.dumps({"text": text, "alignment": d["alignment"]}))
    return mp3, js, len(text)


# ----------------------------------------------------------------------------- timing
def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def plan(n, ch):
    """Splice the chapter narration with scene pauses; return the timeline and caption words."""
    text, starts, cues = chapter_text(ch)
    mp3, js = cache_paths(n, text)
    al = json.loads(js.read_text())["alignment"]
    chars = al["characters"]
    if "".join(chars) != text:
        raise SystemExit(f"chapter {n}: alignment text differs from narration")
    t0s, t1s = al["character_start_times_seconds"], al["character_end_times_seconds"]

    BUILD.mkdir(parents=True, exist_ok=True)
    wav = BUILD / f"chapter_{n:02d}_src.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp3), "-ac", "1", "-ar", str(RATE), str(wav)], check=True)
    with wave.open(str(wav)) as w:
        pcm = w.readframes(w.getnframes())
    audio_len = len(pcm) / 2 / RATE

    def first_char(i):
        while i < len(text) and text[i].isspace():
            i += 1
        return i

    # cut points in source audio: midway between the previous scene's last sound and this scene's first
    cuts = [0.0]
    for s in starts[1:]:
        j = s - 1
        while j > 0 and text[j].isspace():
            j -= 1
        k = first_char(s)
        cuts.append((t1s[j] + t0s[k]) / 2)
    cuts.append(audio_len)

    def src_to_video(t):
        k = max(i for i in range(len(starts)) if cuts[i] <= t or i == 0)
        return LEAD + k * PAD + t

    out = bytearray(b"\0\0" * int(LEAD * RATE))
    scenes = []
    for i, (sid, _) in enumerate(ch["scenes"]):
        if i:
            out += b"\0\0" * int(PAD * RATE)
        a, b = int(cuts[i] * RATE), int(cuts[i + 1] * RATE)
        start = len(out) / 2 / RATE
        out += pcm[a * 2:b * 2]
        scene_start = (start - PAD) if i else LEAD
        cue_t = {}
        for no, idx in cues[i].items():
            cue_t[no] = round(src_to_video(t0s[first_char(idx)]) - 0.12 - scene_start, 3)
        scenes.append({"id": sid, "start": round(scene_start, 3), "cues": cue_t})
    out += b"\0\0" * int(TAIL * RATE)
    duration = len(out) / 2 / RATE
    for i, sc in enumerate(scenes):
        sc["end"] = round(scenes[i + 1]["start"] if i + 1 < len(scenes) else duration, 3)

    spliced = BUILD / f"chapter_{n:02d}.wav"
    with wave.open(str(spliced), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(out))

    words, cur = [], None
    for i, c in enumerate(text):
        if c.isspace():
            cur = None
            continue
        if cur is None:
            cur = {"w": "", "t0": src_to_video(t0s[i])}
            words.append(cur)
        cur["w"] += c
        cur["t1"] = src_to_video(t1s[i])

    timeline = {"chapter": n, "title": ch["title"], "tag": ch["tag"], "duration": round(duration, 3),
                "fps": FPS, "scenes": scenes}
    (BUILD / f"chapter_{n:02d}.timeline.json").write_text(json.dumps(timeline, indent=1))
    (BUILD / f"chapter_{n:02d}.words.json").write_text(json.dumps(words))
    return timeline, spliced


# ----------------------------------------------------------------------------- render
def render(n, ch):
    timeline, wav = plan(n, ch)
    out = VIDEO / f"chapter_{n:02d}.mp4"
    subprocess.run(["node", str(SRC / "render.js"), str(BUILD / f"chapter_{n:02d}.timeline.json"), str(wav), str(out)],
                   check=True)
    return out


# ----------------------------------------------------------------------------- captions
def caption_chunks(words, max_chars=78):
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        line = " ".join(x["w"] for x in cur)
        end = w["w"][-1] in ".?!"
        soft = w["w"][-1] in ",:;" and len(line) > 40
        if end or soft or len(line) > max_chars - 10:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def wrap2(text, width=44):
    if len(text) <= width:
        return [text]
    best = min((i for i, c in enumerate(text) if c == " "), key=lambda i: abs(i - len(text) / 2))
    return [text[:best], text[best + 1:]]


def stamp(t, ass=False):
    h, rem = divmod(max(t, 0), 3600)
    m, s = divmod(rem, 60)
    if ass:
        return f"{int(h)}:{int(m):02d}:{s:05.2f}"
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)) % 1000:03d}"


def captions():
    offset, cues = 0.0, []
    for n in range(1, len(CHAPTERS) + 1):
        words = json.loads((BUILD / f"chapter_{n:02d}.words.json").read_text())
        for ch in caption_chunks(words):
            cues.append([offset + ch[0]["t0"], offset + ch[-1]["t1"] + 0.35, " ".join(w["w"] for w in ch)])
        offset += probe(VIDEO / f"chapter_{n:02d}.mp4")
    for a, b in zip(cues, cues[1:]):
        a[1] = min(a[1], b[0] - 0.02)
    srt = []
    for i, (a, b, t) in enumerate(cues, 1):
        srt.append(f"{i}\n{stamp(a)} --> {stamp(b)}\n" + "\n".join(wrap2(t)) + "\n")
    (VIDEO / "captions.srt").write_text("\n".join(srt), encoding="utf-8")
    ass = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080", "WrapStyle: 2", "",
           "[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
           "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
           "MarginR, MarginV, Encoding",
           "Style: Default,Inter,46,&H00FFFFFF,&H00FFFFFF,&H00000000,&H99000000,0,0,0,0,100,100,0,0,3,14,0,2,160,160,"
           "34,1", "", "[Events]",
           "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for a, b, t in cues:
        ass.append(f"Dialogue: 0,{stamp(a, True)},{stamp(b, True)},Default,,0,0,0,,{chr(92).join(['', 'N']).join(wrap2(t))}")
    (BUILD / "captions.ass").write_text("\n".join(ass) + "\n", encoding="utf-8")


def full():
    captions()
    lst = BUILD / "concat.txt"
    lst.write_text("".join(f"file '{VIDEO / f'chapter_{n:02d}.mp4'}'\n" for n in range(1, len(CHAPTERS) + 1)))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-vf", f"ass={BUILD / 'captions.ass'}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(VIDEO / "full.mp4")],
                   check=True)


def frames():
    d = BUILD / "frames"
    d.mkdir(parents=True, exist_ok=True)
    for n in range(1, len(CHAPTERS) + 1):
        tl = json.loads((BUILD / f"chapter_{n:02d}.timeline.json").read_text())
        shots = [("title", LEAD - 0.4)] + [(s["id"], s["end"] - 0.35) for s in tl["scenes"]]
        for sid, t in shots:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(VIDEO / f"chapter_{n:02d}.mp4"),
                            "-frames:v", "1", "-vf", "scale=960:-1", str(d / f"{n:02d}_{sid}.png")], check=True)


def script_md():
    lines = ["# Ghost Data Still Exists - explainer video narration", "",
             f"Voice: ElevenLabs \"{VOICE_NAME}\" (`{VOICE_ID}`), model `{MODEL_ID}`. "
             "Generated from `video/src/chapters.py`; cue markers are removed.", ""]
    for n, ch in enumerate(CHAPTERS, 1):
        lines += [f"## Chapter {n} - {ch['title']} ({ch['tag'].lower()})", ""]
        for _, raw in ch["scenes"]:
            lines += [CUE.sub("", raw), ""]
    (VIDEO / "script.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    only = [int(x) for x in sys.argv[2:]] or list(range(1, len(CHAPTERS) + 1))
    script_md()
    if step in ("tts", "all"):
        spent = 0
        for n in only:
            _, _, c = tts(n, CHAPTERS[n - 1])
            spent += c
            print(f"chapter {n}: {'synthesised ' + str(c) + ' chars' if c else 'cached'}")
        print(f"characters sent this run: {spent}")
    if step in ("render", "all"):
        with ThreadPoolExecutor(max_workers=3) as ex:
            for out in ex.map(lambda n: render(n, CHAPTERS[n - 1]), only):
                print(out, f"{probe(out):.2f}s")
    if step in ("full", "all"):
        full()
        print(VIDEO / "full.mp4", f"{probe(VIDEO / 'full.mp4'):.2f}s")
    if step in ("frames", "all"):
        frames()


if __name__ == "__main__":
    main()
