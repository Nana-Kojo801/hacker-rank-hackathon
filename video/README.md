# Explainer video

An 8-chapter, about 11-minute explainer of the Ghost Data Still Exists problem and this repository's solution.

| file | what it is |
| --- | --- |
| `script.md` | the exact narration, by chapter (generated from `src/chapters.py`) |
| `captions.srt` | captions for `full.mp4` |
| `src/chapters.py` | narration split into scenes; `[n]` markers are animation cues |
| `src/scenes.html` | every scene as HTML/CSS/SVG plus the small seek-by-time animation runtime |
| `src/render.js` | drives `scenes.html` frame by frame in Playwright/Chromium and pipes frames to ffmpeg |
| `src/preview.js` | renders one still per scene for layout checks |
| `src/build.py` | narration (ElevenLabs) -> timing -> render -> captions -> `full.mp4` |

The MP4s (`chapter_01.mp4` ... `chapter_08.mp4`, `full.mp4`), the narration cache (`cache/`) and the build intermediates
(`build/`) are not committed.

## Rebuild

```bash
export ELEVENLABS_API_KEY=...          # only needed if the narration text changed
python3 video/src/build.py all          # tts (cached) -> render -> full.mp4 -> QA frames
```

Steps can also run one at a time: `tts`, `render`, `full`, `frames`, optionally followed by chapter numbers
(`python3 video/src/build.py render 3 4`).

How sync works: each chapter is synthesised in one ElevenLabs call with character timestamps. Scene changes are cut in
the silence between sentences, with a short pause added, and every `[n]` cue in the text becomes the time that phrase is
spoken, so the scene reveals its element on the word. Captions come from the same timestamps.

Changing only cue markers or `scenes.html` costs no ElevenLabs credits; changing narration words re-synthesises that chapter.
