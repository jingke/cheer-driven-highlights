#!/usr/bin/env python3
"""程序化合成"卡点配乐"并与现场欢呼声做闪避混音。

为什么需要：本机常常没有可用音乐素材，也没有音乐生成服务，而用户要求"配上
匹配的音乐"。本脚本用 numpy 直接合成一段原创配乐（无版权问题），并让每个
剪辑点都有一次和弦推进 + impact，从而与画面节奏严格对齐。

混音原则（实测教训）：进球集锦里**欢呼声是关键声音证据**，音乐只能做背景层。
早期版本把音乐混得太响（music*0.62 / field*0.90），现场声相关性仅 0.213、
欢呼被淹没。当前默认 field*1.35 + music*0.40*duck，欢呼响时音乐降到 20%。

用法：
  python bgm.py --video out/高光集.mp4 --plan work/final.json \
      --out out/高光集_配乐.mp4 [--music-out work/music.wav]
  # plan 也可传 highlights.json（用全部 candidates）
"""
import argparse
import json
import os
import subprocess
import sys
import wave
from functools import lru_cache

import numpy as np

SR = 48000
XD = 0.30                       # 与 assemble*.py 的 xfade 时长保持一致
BPM = 120.0
BEAT = 60.0 / BPM
BAR = 4 * BEAT

FF = (os.environ.get("FFMPEG") or "/opt/homebrew/bin/ffmpeg")

rng = np.random.default_rng(20261106)
L = np.zeros(0, np.float32)
R = np.zeros(0, np.float32)
N = 0


def init(total):
    global L, R, N
    N = int(SR * total)
    L = np.zeros(N, np.float32)
    R = np.zeros(N, np.float32)


def add(t, sig, gain=1.0, pan=0.0):
    i = int(round(t * SR))
    if i >= N or i < 0:
        return
    j = min(N, i + len(sig))
    seg = sig[: j - i] * gain
    L[i:j] += seg * (1.0 - 0.35 * pan)
    R[i:j] += seg * (1.0 + 0.35 * pan)


def noise(n):
    return rng.standard_normal(n).astype(np.float32)


def env_exp(n, tau):
    return np.exp(-np.arange(n, dtype=np.float32) / (SR * tau))


@lru_cache(maxsize=8)
def kick():
    n = int(SR * 0.30)
    t = np.arange(n) / SR
    f = 45 + 95 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * env_exp(n, 0.075)).astype(np.float32) * 0.95


@lru_cache(maxsize=8)
def snare():
    n = int(SR * 0.20)
    x = np.diff(np.concatenate([[0.0], noise(n) * env_exp(n, 0.055)])).astype(np.float32)
    y = np.zeros(n, np.float32)
    for _ in range(2):
        acc = 0.0
        for k in range(n):
            acc += 0.45 * (x[k] - acc)
            y[k] = acc
        x = y.copy()
    body = np.sin(2 * np.pi * 185 * np.arange(n) / SR) * env_exp(n, 0.035)
    return (y * 2.2 + body * 0.22).astype(np.float32) * 0.55


@lru_cache(maxsize=8)
def hat(open_=False):
    n = int(SR * (0.13 if open_ else 0.045))
    x = np.diff(np.concatenate([[0.0], noise(n)])).astype(np.float32)
    return (x * env_exp(n, 0.055 if open_ else 0.016)).astype(np.float32) * 0.16


@lru_cache(maxsize=16)
def bass(freq, dur):
    n = int(SR * dur)
    t = np.arange(n) / SR
    saw = np.tanh(np.sin(2 * np.pi * freq * t) * 2.2).astype(np.float32)
    y = np.zeros(n, np.float32)
    acc = 0.0
    for k in range(n):
        acc += 0.06 * (saw[k] - acc)
        y[k] = acc
    return (y * env_exp(n, dur * 0.55) * 1.8).astype(np.float32) * 0.40


@lru_cache(maxsize=16)
def pad(freqs, dur):
    freqs = tuple(freqs)
    n = int(SR * dur)
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    for k, f in enumerate(freqs):
        det = 1.0 + (k - 1) * 0.0015
        out += np.sin(2 * np.pi * f * det * t + k * 0.7).astype(np.float32)
        out += 0.30 * np.sin(2 * np.pi * f * 2 * t).astype(np.float32)
    atk = np.clip(np.arange(n) / (SR * 0.35), 0, 1)
    rel = np.clip((n - np.arange(n)) / (SR * 0.6), 0, 1)
    return (out / (len(freqs) * 1.5) * atk * rel).astype(np.float32) * 0.20


def pluck(freq, dur=0.22):
    n = int(SR * dur)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * freq * 2 * t)
    return (s * env_exp(n, 0.055)).astype(np.float32) * 0.13


def impact():
    n = int(SR * 1.5)
    t = np.arange(n) / SR
    f = 38 + 30 * np.exp(-t * 8)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, 0.42)
    return (boom * 0.85 + noise(n) * env_exp(n, 0.30) * 0.30).astype(np.float32) * 0.75


def riser(dur=0.9):
    n = int(SR * dur)
    return (noise(n) * np.linspace(0.02, 1.0, n) ** 2 * 0.16).astype(np.float32)


# A 小调：Am - F - C - G
CHORDS = [
    (110.00, (220.00, 261.63, 329.63, 440.00)),
    (87.31,  (174.61, 220.00, 261.63, 349.23)),
    (130.81, (261.63, 329.63, 392.00, 523.25)),
    (98.00,  (196.00, 246.94, 293.66, 392.00)),
]


def compose(total, nseg, seg):
    """按 nseg 个片段（每段有效时长 seg）生成卡点配乐。"""
    init(total)
    for si in range(nseg):
        start = si * seg
        root, notes = CHORDS[si % 4]
        g = 0.72 if si == 0 else (0.90 if si == nseg - 1 else 1.0)
        # 卡点：片段起点 impact + 强拍（段间隔过短时降密度）
        if seg >= 6.0:
            add(start, impact(), 0.85 * g)
            add(start, kick(), 1.0 * g)
            if si > 0:
                add(start - 0.9, riser(0.9), 0.9 * g)
        nbars = max(1, int((seg - 0.5) // BAR))
        for b in range(nbars):
            b0 = start + b * BAR
            add(b0, pad(notes[1:], BAR * 0.98), 1.0 * g,
                pan=0.6 if b % 2 else -0.6)
            for beat in range(4):
                t = b0 + beat * BEAT
                add(t, kick() if beat % 2 == 0 else snare(), 0.80 * g)
                add(t, bass(root, BEAT * 0.9), 0.85 * g)
                add(t, hat(False), 0.8 * g, pan=-0.4)
                add(t + BEAT / 2, hat(False), 0.65 * g, pan=0.4)
            if si >= 1 and b >= 1:
                for k in range(8):
                    nt = notes[k % 3] * (2 if (k // 3) % 2 else 1)
                    add(b0 + k * BAR / 8, pluck(nt), 0.9 * g,
                        pan=0.5 if k % 2 else -0.5)
    fo = int(SR * max(0.0, total - 3.0))
    fade = np.linspace(1.0, 0.0, N - fo).astype(np.float32)
    L[fo:] *= fade
    R[fo:] *= fade
    music = np.tanh(np.stack([L, R], axis=1) * 1.15).astype(np.float32)
    return music / max(float(np.abs(music).max()), 1e-6) * 0.82


def write_wav(path, arr):
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(arr, -1, 1) * 32767).astype(np.int16).tobytes())


def read_wav(path):
    with wave.open(path, "rb") as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0
        return x.reshape(-1, 2)


def mix(video, music, out_wav, field_gain=1.35, music_gain=0.40, duck_depth=0.80):
    """提取现场声 → 按 20ms RMS 做闪避 → 混合。"""
    tmp = out_wav + ".field.wav"
    subprocess.run([FF, "-hide_banner", "-nostdin", "-y", "-i", video,
                    "-vn", "-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le", tmp],
                   check=True, capture_output=True)
    field = read_wav(tmp)[: len(music)]
    if len(field) < len(music):
        field = np.pad(field, ((0, len(music) - len(field)), (0, 0)))
    hop = int(SR * 0.02)
    mono = field.mean(axis=1)
    nb = len(mono) // hop
    rms = np.sqrt((mono[: nb * hop].reshape(nb, hop) ** 2).mean(axis=1) + 1e-9)
    rms = np.maximum(rms - np.percentile(rms, 50), 0)
    rms = np.clip(rms / max(np.percentile(rms, 98), 1e-6), 0, 1)
    sm = np.zeros(nb, np.float32)
    acc = 0.0
    for k, v in enumerate(rms):
        acc += (0.55 if v > acc else 0.05) * (v - acc)
        sm[k] = acc
    duck = 1.0 - duck_depth * sm
    duck = np.repeat(duck, hop)[: len(music)]
    if len(duck) < len(music):
        duck = np.pad(duck, (0, len(music) - len(duck)), constant_values=duck[-1])
    duck = np.convolve(duck, np.ones(64) / 64, mode="same").astype(np.float32)
    m = np.tanh(field * field_gain + music * (music_gain * duck[:, None]))
    write_wav(out_wav, m / max(float(np.abs(m).max()), 1e-6) * 0.94)
    os.remove(tmp)
    return float(duck.min()), float(duck.max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="已合成的成片（含现场声）")
    ap.add_argument("--plan", required=True,
                    help="final.json 或 highlights.json，用于取片段数与时长")
    ap.add_argument("--out", required=True, help="最终配乐成片")
    ap.add_argument("--music-out", default=None, help="可选：另存纯音乐轨 WAV")
    ap.add_argument("--field-gain", type=float, default=1.35)
    ap.add_argument("--music-gain", type=float, default=0.40)
    ap.add_argument("--duck-depth", type=float, default=0.80)
    a = ap.parse_args()

    d = json.load(open(a.plan))
    sel = d.get("selected") or d.get("candidates")
    nseg = len(sel)
    if not nseg:
        sys.exit("plan 里没有 selected/candidates")
    clip_dur = float(sel[0].get("clip_dur", d.get("pre_s", 5) + d.get("post_s", 8)))
    seg = clip_dur - XD
    total = nseg * clip_dur - (nseg - 1) * XD
    print(f"片段 {nseg} 段，每段 {clip_dur}s，卡点间隔 {seg:.2f}s，总时长 {total:.1f}s")

    music = compose(total, nseg, seg)
    if a.music_out:
        write_wav(a.music_out, music)
        print("纯音乐轨:", a.music_out)

    mixwav = os.path.splitext(a.out)[0] + ".mix.wav"
    lo, hi = mix(a.video, music, mixwav, a.field_gain, a.music_gain, a.duck_depth)
    print(f"闪避范围 {lo:.2f}~{hi:.2f}")

    subprocess.run([FF, "-hide_banner", "-nostdin", "-y", "-i", a.video,
                    "-i", mixwav, "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy",
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,"
                           "alimiter=limit=0.97:level=disabled:attack=5:release=80",
                    "-c:a", "aac", "-b:a", "192k", "-ar", str(SR),
                    "-movflags", "+faststart", a.out], check=True, capture_output=True)
    print("输出:", a.out)


if __name__ == "__main__":
    main()
