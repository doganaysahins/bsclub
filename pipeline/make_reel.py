#!/usr/bin/env python3
"""Build a Backstory Club comic reel from a JSON spec.

usage: python3 pipeline/make_reel.py pipeline/specs/<slug>.json
Outputs videos/<slug>.mp4 and covers/tile_<name>.jpg (paths from the spec).
Needs: kokoro-onnx + soundfile (pip), model files in $KOKORO_DIR
(kokoro-v1.0.onnx, voices-v1.0.bin from github.com/thewh1teagle/kokoro-onnx releases),
node + playwright, ffmpeg.
"""
import json, os, sys, subprocess, shutil, tempfile, html
import numpy as np, soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FPS = 30
PAD_BEFORE, PAD_AFTER = 0.15, 0.45

def tts(scenes, voice, speed, work):
    from kokoro_onnx import Kokoro
    kd = os.environ.get("KOKORO_DIR", os.path.join(HERE, ".kokoro"))
    k = Kokoro(os.path.join(kd, "kokoro-v1.0.onnx"), os.path.join(kd, "voices-v1.0.bin"))
    chunks, starts, t, sr = [], [], 0.0, 24000
    for s in scenes:
        audio, sr = k.create(s["say"], voice=voice, speed=speed, lang="en-us")
        seg = np.concatenate([np.zeros(int(PAD_BEFORE * sr)), audio, np.zeros(int(PAD_AFTER * sr))])
        starts.append(round(t, 3)); t += len(seg) / sr; chunks.append(seg)
    tail = np.zeros(int(0.8 * sr)); chunks.append(tail); t += 0.8
    wav = os.path.join(work, "voice.wav")
    sf.write(wav, np.concatenate(chunks).astype(np.float32), sr)
    return wav, starts, t

def build_html(spec, starts, total, path):
    scenes = []
    for i, s in enumerate(spec["scenes"]):
        cap = html.escape(s.get("caption", s["say"]))
        alt = " alt" if i % 2 else ""
        scenes.append(f'<div class="scene{alt}" data-start="{starts[i]}"><div class="stage">{s["html"]}</div>'
                      f'<div class="cap pop">{cap}</div></div>')
    c = spec["cover"]
    cover = (f'<div class="scene" id="cover"><div class="stage" style="top:420px;gap:40px">'
             f'<div class="kicker">{c["kicker"]}</div><div class="big tilt" style="font-size:{c.get("size",300)}px">{c["title"]}</div>'
             f'<div class="rule"></div><div class="kicker">{c["sub"]}</div>'
             f'<div class="logo" style="margin-top:120px">Bc<i>.</i></div></div></div>')
    js = """
const S=[...document.querySelectorAll('.scene[data-start]')];
function ease(x){x=Math.min(Math.max(x,0),1);const c=1.70158;return 1+(c+1)*Math.pow(x-1,3)+c*Math.pow(x-1,2);}
window.setT=function(t){let cur=0;S.forEach((s,i)=>{if(+s.dataset.start<=t+1e-6)cur=i;});
 S.forEach((s,i)=>{s.style.display=i===cur?'block':'none';});
 const s=S[cur],lt=t-(+s.dataset.start);
 const pops=[...s.querySelectorAll('.stage .pop'),...s.querySelectorAll('.cap')];
 pops.forEach((el,j)=>{const d=(el.classList.contains('cap')?0.05:0.12+j*0.16);const p=(lt-d)/0.38;
  const base=el.dataset.base||(el.dataset.base=getComputedStyle(el).transform==='none'?'':getComputedStyle(el).transform);
  if(p<=0){el.style.opacity=0;return;}el.style.opacity=Math.min(1,p*3);
  const sc=0.55+0.45*ease(p);el.style.transform=(base&&base!=='none'?base+' ':'')+'scale('+sc+')';});};
window.showCover=function(){S.forEach(s=>s.style.display='none');document.getElementById('cover').style.display='block';};
"""
    doc = (f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{HERE}/comic.css"></head>'
           f'<body>{"".join(scenes)}{cover}<script>{js}</script></body></html>')
    open(path, "w").write(doc)

def main(spec_path):
    spec = json.load(open(spec_path))
    work = tempfile.mkdtemp(prefix="reel_")
    wav, starts, total = tts(spec["scenes"], spec.get("voice", "am_michael"), spec.get("speed", 1.05), work)
    # background melody: unique per reel (seeded by slug), ducked under the voice
    sys.path.insert(0, HERE); import music
    import zlib
    mixed = os.path.join(work, "mix.wav")
    print("music:", music.mix(wav, mixed, zlib.crc32(spec["slug"].encode())))
    wav = mixed
    page = os.path.join(work, "page.html"); build_html(spec, starts, total, page)
    cover = os.path.join(ROOT, spec["cover_path"])
    json.dump({"starts": starts, "total": total, "cover": cover}, open(os.path.join(work, "tl.json"), "w"))
    frames = os.path.join(work, "frames")
    subprocess.run(["node", os.path.join(HERE, "render_frames.js"), page, os.path.join(work, "tl.json"), frames, str(FPS)], check=True)
    out = os.path.join(ROOT, spec["video_path"])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(frames, "f%05d.jpg"), "-i", wav,
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
                    "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-af", "loudnorm=I=-14:TP=-1.5", "-shortest",
                    "-movflags", "+faststart", out], check=True)
    shutil.rmtree(work)
    print(json.dumps({"video": out, "cover": cover, "duration": round(total, 2)}))

if __name__ == "__main__":
    main(sys.argv[1])
