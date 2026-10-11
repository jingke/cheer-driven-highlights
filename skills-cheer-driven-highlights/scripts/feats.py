#!/usr/bin/env python3
"""流式提取音频特征（不整体载入 WAV，避免内存爆）。

特征（帧=20ms, win=1024 @16k）：
  db   : 逐帧 RMS 能量(dB)
  band : 400-3000Hz 频带能量占比（人群欢呼核心频段）
  flat : 谱平坦度（接近 1=噪声，低=有谐波的人声/音乐）
  cent : 谱质心(Hz)，高=尖叫/高频噪声
  zcr  : 过零率（高频噪声 vs 低频嗡嗡）
  base : 10s 滚动 20 百分位基线（当地环境底噪）

为何 16k 单声道：只需能量/频段分布，16k 足够覆盖欢呼主频段(0.3-6k)，
单声道省一半算力；采样率≠源没关系（检测只看相对变化）。
"""
import argparse
import os
import shutil
import wave

import numpy as np

SR = 16000
HOP = 320      # 20 ms
WIN = 1024


def find_ffmpeg():
    return (os.environ.get("FFMPEG") or shutil.which("ffmpeg")
            or "/opt/homebrew/bin/ffmpeg")


def extract_audio(video, wav_out, ffmpeg=None):
    """用 ffmpeg 从视频抽 16k 单声道 WAV。"""
    ff = ffmpeg or find_ffmpeg()
    import subprocess
    cmd = [ff, "-hide_banner", "-nostdin", "-y", "-i", video,
           "-vn", "-map", "0:a:0", "-ac", "1", "-ar", str(SR),
           "-c:a", "pcm_s16le", wav_out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"音频提取失败: {r.stderr[-1500:]}")
    return wav_out


def stream_feats(path, chunk_s=60.0):
    """边读边算，返回逐帧特征。内存 = chunk + 特征数组(很小)。"""
    win = np.hanning(WIN).astype(np.float32)
    freqs = np.fft.rfftfreq(WIN, 1.0 / SR)
    b_lo = np.searchsorted(freqs, 400)
    b_hi = np.searchsorted(freqs, 3000)

    out = {k: [] for k in ("db", "band", "flat", "cent", "zcr")}
    with wave.open(path, "rb") as w:
        assert w.getsampwidth() == 2, "需要 16-bit PCM"
        sr = w.getframerate()
        total = w.getnframes()
        nchunk = int(chunk_s * sr)
        carry = np.zeros(0, np.float32)
        read = 0
        while read < total:
            n = min(nchunk, total - read)
            raw = w.readframes(n)
            read += n
            x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            if carry.size:
                x = np.concatenate([carry, x])
            nfr = 1 + (len(x) - WIN) // HOP
            if nfr <= 0:
                carry = x
                continue
            need = (nfr - 1) * HOP + WIN
            seg = x[:need]
            blk = np.lib.stride_tricks.as_strided(
                seg, shape=(nfr, WIN),
                strides=(seg.strides[0] * HOP, seg.strides[0]))
            blk = np.array(blk, dtype=np.float32) * win

            sp = np.abs(np.fft.rfft(blk, axis=1)) ** 2
            tot = sp.sum(axis=1) + 1e-12
            db = 20 * np.log10(np.sqrt((blk ** 2).mean(axis=1)) + 1e-9)
            band = sp[:, b_lo:b_hi].sum(axis=1) / tot
            hs = sp.copy()
            hs[:, :b_lo] = 0.0
            cent = (hs * freqs[None, :]).sum(axis=1) / (hs.sum(axis=1) + 1e-12)
            gm = np.exp(np.log(sp + 1e-12).mean(axis=1))
            flat = gm / (sp.mean(axis=1) + 1e-12)
            zcr = (np.diff(np.sign(blk), axis=1) != 0).mean(axis=1)

            out["db"].append(db.astype(np.float32))
            out["band"].append(band.astype(np.float32))
            out["flat"].append(flat.astype(np.float32))
            out["cent"].append(cent.astype(np.float32))
            out["zcr"].append(zcr.astype(np.float32))
            carry = x[(nfr - 1) * HOP + WIN:]
            del blk, sp, hs

    res = {k: np.concatenate(v) for k, v in out.items()}
    res["hop_s"] = HOP / SR
    res["duration"] = total / sr
    return res


def block_baseline(v, hop_s, win_s=10.0, pct=20.0):
    """分段百分位基线 + 插值，O(n)。"""
    n = len(v)
    W = max(1, int(win_s / hop_s))
    nb = max(1, int(np.ceil(n / W)))
    centers, vals = [], []
    for i in range(nb):
        seg = v[i * W:(i + 1) * W]
        if len(seg) == 0:
            continue
        centers.append((i + 0.5) * W)
        vals.append(np.percentile(seg, pct))
    return np.interp(np.arange(n), centers, vals).astype(np.float32)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("-o", "--npz", required=True)
    a = ap.parse_args()
    f = stream_feats(a.wav)
    base = block_baseline(f["db"], f["hop_s"])
    np.savez_compressed(
        a.npz, hop_s=f["hop_s"], duration=f["duration"],
        **{k: f[k] for k in ("db", "band", "flat", "cent", "zcr")},
        base=base,
    )
    print(f"{a.wav}  {f['duration']/60:.1f} min  frames={len(f['db'])}")
    for k in ("db", "band", "flat", "cent", "zcr"):
        q = np.percentile(f[k], [5, 25, 50, 75, 95, 99])
        print(f"  {k:5s} p5={q[0]:9.4f} p25={q[1]:9.4f} p50={q[2]:9.4f} "
              f"p75={q[3]:9.4f} p95={q[4]:9.4f} p99={q[5]:9.4f}")
    print(f"  base  p50={np.percentile(base,50):.2f}dB")
    rise = f["db"] - base
    print(f"  rise  p50={np.percentile(rise,50):.2f} p90={np.percentile(rise,90):.2f} "
          f"p99={np.percentile(rise,99):.2f} max={rise.max():.2f}")
