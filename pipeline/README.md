# Backstory Club reel pipeline

Comic-style 1080x1920 reels with their own voiceover (Kokoro TTS, voice `am_michael`), rendered from a JSON spec.

## Setup (fresh container)
```bash
pip install -q kokoro-onnx soundfile --break-system-packages
mkdir -p pipeline/.kokoro && cd pipeline/.kokoro
curl -sL -O https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -sL -O https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
cd ../..
```
Node + playwright and ffmpeg must be available.

## Make a reel
1. Write `pipeline/specs/<slug>_comic.json` (copy `grace_comic.json` or `parkrun_comic.json`).
   - `say` is the spoken line (write numbers/dates as words), `caption` the on-screen text (defaults to `say`).
   - `html` uses classes from `comic.css`: `kicker`, `big` (+`huge`/`mid`/`small`, `white`, `tilt`), `label`, `chip` (`chip w`), `card`, `row`, `strike`, `logo`. Add `pop` to each element that should pop in.
   - Keep big words short; long titles need `mid` or an inline `font-size`.
2. `python3 pipeline/make_reel.py pipeline/specs/<slug>_comic.json` → `videos/<slug>_comic.mp4` + cover.
3. Check frames (`ffmpeg -i video -vf "fps=1/3.6,scale=216:-1,tile=6x2" sheet.jpg`) for overflow / wrapping.
4. Commit + push, then post with Windsor `create_video_post` using raw URLs pinned to the commit SHA:
   `https://raw.githubusercontent.com/doganaysahins/bsclub/<sha>/videos/<file>.mp4` and the cover as `cover_url`.
5. Add a line to `posted.md`.

## Rules (from the owner)
- English, endurance/fitness niche (running, marathons, triathlon, CrossFit, weightlifting).
- Each series keeps its starting style: Running Backstories and The Girls are both Comic.
- Every reel MUST have a background melody under the voiceover (`music.py`, mixed automatically by `make_reel.py`, unique per slug). Never post a reel without it.
- Every reel has its own voiceover; never reuse another video's audio. Do not use eachlabs.
- Only verified facts (check with web sources); skip anything uncertain.
- Cover: big title on plain background, same style as its video.
