#!/usr/bin/env python3
"""Generate a unique upbeat background bed for each reel and mix it under the voice.

Every call with a different seed gives a different key, tempo, progression and
arrangement, so no two reels share the same music.

usage: python3 pipeline/music.py <voice.wav> <out.wav> <seed>
"""
import sys, zlib
import numpy as np, soundfile as sf

SR = 48000
KEYS = {"A": 55.0, "C": 65.41, "D": 73.42, "E": 41.20, "F": 43.65, "G": 49.0}
PROGS = [[0, 5, 3, 4], [0, 3, 4, 3], [0, 4, 5, 3], [5, 3, 0, 4], [0, 5, 0, 4], [0, 3, 5, 4]]
MINOR = [0, 2, 3, 5, 7, 8, 10]
MAJOR = [0, 2, 4, 5, 7, 9, 11]

def lp(x, a):  # one-pole low-pass
    y = np.empty_like(x); s = 0.0
    for i in range(len(x)):
        s += a * (x[i] - s); y[i] = s
    return y

def lp_fast(x, cutoff):
    # FFT low-pass for long signals
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x))

def hp_fast(x, cutoff):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (cutoff / np.maximum(f, 1)) ** 4)
    return np.fft.irfft(X, len(x))

def saw(freq, n, detune=0.0):
    t = np.arange(n) / SR
    return 2 * ((t * freq * (1 + detune)) % 1) - 1

def make_bed(duration, seed):
    rng = np.random.default_rng(seed)
    key = rng.choice(list(KEYS)); root = KEYS[key]
    scale = MINOR if rng.random() < 0.7 else MAJOR
    prog = PROGS[rng.integers(len(PROGS))]
    bpm = int(rng.integers(96, 116)); beat = 60 / bpm; bar = 4 * beat
    n = int((duration + 1) * SR)
    out = np.zeros(n); bass = np.zeros(n); pad = np.zeros(n); arp = np.zeros(n); drums = np.zeros(n)

    def note(deg, octave):
        semis = scale[deg % 7] + 12 * (deg // 7) + 12 * octave
        return root * 2 ** (semis / 12)

    arp_pat = rng.permutation([0, 2, 4, 7])[:4]
    nbars = int(np.ceil(duration / bar)) + 1
    for b in range(nbars):
        deg = prog[b % len(prog)]; start = int(b * bar * SR); L = int(bar * SR)
        if start >= n: break
        L = min(L, n - start)
        # pad: triad, detuned saws, slow attack
        env = np.minimum(1, np.arange(L) / (0.25 * SR)) * np.minimum(1, (L - np.arange(L)) / (0.1 * SR))
        chord = sum(saw(note(deg + d, 2), L, dt) for d in (0, 2, 4) for dt in (-0.004, 0.004))
        pad[start:start + L] += chord * env * 0.05
        # bass: eighth-note pulses on root
        for e in range(8):
            s0 = start + int(e * beat / 2 * SR); l = int(beat / 2 * SR * 0.9)
            if s0 + l > n: break
            ev = np.exp(-np.arange(l) / (0.18 * SR))
            bass[s0:s0 + l] += saw(note(deg, 0), l) * ev * 0.35
        # arp: 16ths plucks
        for e in range(16):
            s0 = start + int(e * beat / 4 * SR); l = int(beat / 4 * SR)
            if s0 + l > n: break
            f = note(deg + arp_pat[e % 4], 3 + (e // 8) % 2)
            tt = np.arange(l) / SR
            arp[s0:s0 + l] += np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.09) * 0.12
        # drums
        for q in range(4):
            s0 = start + int(q * beat * SR)
            if s0 + int(0.3 * SR) > n: break
            tt = np.arange(int(0.3 * SR)) / SR
            if q in (0, 2) or rng.random() < 0.15:  # kick
                drums[s0:s0 + len(tt)] += np.sin(2 * np.pi * (50 + 90 * np.exp(-tt / 0.03)) * tt) * np.exp(-tt / 0.12) * 0.7
            if q in (1, 3):  # clap
                l = int(0.18 * SR); nz = rng.standard_normal(l) * np.exp(-np.arange(l) / (0.04 * SR))
                drums[s0:s0 + l] += nz * 0.18
            for h in (0, 1):  # hats
                hs = s0 + int(h * beat / 2 * SR); l = int(0.05 * SR)
                if hs + l < n:
                    drums[hs:hs + l] += rng.standard_normal(l) * np.exp(-np.arange(l) / (0.012 * SR)) * 0.06
    pad = lp_fast(pad, 1800); bass = lp_fast(bass, 400); drums[:] = drums
    hats_hp = hp_fast(drums, 30)
    out = pad + bass + arp + hats_hp
    out = out[:int(duration * SR)]
    fade = int(1.2 * SR); out[-fade:] *= np.linspace(1, 0, fade); out[:int(0.05 * SR)] *= np.linspace(0, 1, int(0.05 * SR))
    out /= np.max(np.abs(out)) + 1e-9
    return out, dict(key=key, bpm=bpm, prog=prog, minor=scale is MINOR)

def mix(voice_path, out_path, seed, music_gain=1.0):
    v, sr = sf.read(voice_path)
    if v.ndim > 1: v = v.mean(1)
    if sr != SR:
        idx = np.arange(int(len(v) * SR / sr)) * sr / SR
        v = np.interp(idx, np.arange(len(v)), v)
    bed, info = make_bed(len(v) / SR, seed)
    bed = bed[:len(v)]
    # sidechain: duck music while voice is speaking
    w = int(0.05 * SR)
    env = np.sqrt(np.convolve(v ** 2, np.ones(w) / w, mode="same"))
    speaking = (env > 0.01).astype(float)
    sm = np.convolve(speaking, np.ones(int(0.25 * SR)) / int(0.25 * SR), mode="same")
    gain = 0.34 - 0.14 * np.clip(sm, 0, 1)  # music under voice, a bit louder in gaps
    vnorm = v / (np.max(np.abs(v)) + 1e-9) * 0.9
    m = vnorm + bed * gain * music_gain  # music_gain: optional per-spec trim
    m /= max(1.0, np.max(np.abs(m)) / 0.98)
    sf.write(out_path, m.astype(np.float32), SR)
    return info

if __name__ == "__main__":
    seed = sys.argv[3]
    seed = int(seed) if seed.isdigit() else zlib.crc32(seed.encode())
    print(mix(sys.argv[1], sys.argv[2], seed))
