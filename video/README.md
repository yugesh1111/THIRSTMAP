# The ThirstMap films

`docs/video/thirstmap_film.mp4` (5 min, opening on a cold open) walks through every judging criterion and every Track 2 deliverable;
`docs/video/thirstmap_film_short.mp4` is the 70-second cut. Both are watchable at
https://yugesh1111.github.io/THIRSTMAP/film.html, with subtitles burned in and as caption tracks (`*.vtt`).

How they are made, so they can be remade after any new result:

1. `make_film.py` reads every number from the result files (`results/*/summary.json`, the dataset manifest, the
   errata list, the audit) and **writes every spoken and shown number from them**, so a new result means a new film.
2. It synthesises the narration line by line with Kokoro-82M, an open text-to-speech model that runs locally
   (Apache-2.0; `pip install kokoro soundfile`), and times every scene, caption and animation to the spoken lines.
3. It writes one HTML page per film from real material only: pipeline images, dataset scenes, model answers drawn on
   the images, screenshots of the live demo, the notebook and the human test (`capture/`, made by `capture.js`), and
   the real output of `thirstmap generate` (`capture/gen.txt`).
4. `render_film.js` draws every frame at an exact time (no screen recording, so no dropped frames) and encodes it with
   the narration (H.264, 1080p, 30 fps, loudness-normalised AAC).

## Remaking the films from a fresh clone

The narration needs its own Python 3.12 environment (PyTorch and spaCy, about 1 GB), kept apart from the project's.
Versions are pinned in `requirements-video.txt` (Python) and `package.json` (Playwright 1.49.1, Chromium 131).

```bash
uv venv --python 3.12 ../.venv-video
VIRTUAL_ENV=../.venv-video uv pip install -r video/requirements-video.txt
(cd video && npm ci && npx playwright install chromium)        # ffmpeg must be on PATH too
python video/film_scenes.py                                     # the 11 dataset scenes the films show (~3 min)
../.venv-video/bin/python video/make_film.py --film full --test-python python   # or --film short
node video/render_film.js video/build/full docs/video/thirstmap_film.mp4         # ~15 min on a laptop
node video/render_film.js video/build/full --preview 10,60,120 /tmp/frames      # still frames to check first
```

- `film_scenes.py` and `make_film.py --test-python` run with the project's own environment (the one with
  `requirements-lock.txt` installed). `--test-python` names that interpreter, so the film can say how many tests pytest
  collects instead of a typed-in number.
- `film_scenes.py` rebuilds dataset v1.0 scenes from their seeds into `video/build/dataset/`, so the 2.1 GB release is
  not needed. It needs the DejaVu fonts (Debian: `fonts-dejavu-core`; macOS: `brew install --cask font-dejavu`). On macOS
  about 1% of pixels differ from the release (text anti-aliasing); the scenes and answers are the same.
- The first `make_film.py` run downloads Kokoro-82M (about 330 MB) from Hugging Face; every sentence is then cached in
  `video/build/tts_cache/`. With the same versions, the narration and subtitle timings come out identical to the published film.
- Change the words in `full_script()` / `short_script()`, or the scenes in `page()`; numbers come from the result files.

Fonts: Inter, Space Grotesk, JetBrains Mono (SIL Open Font License, `fonts/`).
