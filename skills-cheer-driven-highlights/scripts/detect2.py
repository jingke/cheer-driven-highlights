#!/usr/bin/env python3
"""欢呼事件检测 v2 —— 基于局部 z-score 复合评分。

为什么用局部 z-score 而非绝对阈值：
  一次足球/演出视频里，环境底噪本身在变（人群嗡嗡、风、解说），
  用全局绝对阈值（如"db>-30"）会误杀或漏检。相对"当地 20~60s 窗口"的
  z-score 才稳定。实测 DJI 夜场素材 flat 中位数仅 0.004、cent ~1056Hz，
  拍脑袋设的固定阈值全部失效（曾导致 0 检出），z-score 自适应解决。

欢呼 = 能量相对当地跃升(rise)为主 + 宽频噪声性(band/flat/cent/zcr)为辅。
"""
import argparse
import json

import numpy as np


def load(p):
    z = np.load(p)
    return {k: z[k] for k in z.files}


def rolling_mean_std(v, win_frames):
    """精确滚动均值/标准差（累积和法，O(n)）。"""
    n = len(v)
    w = min(win_frames, n)
    vf = v.astype(np.float64)
    c1 = np.concatenate([[0.0], np.cumsum(vf)])
    c2 = np.concatenate([[0.0], np.cumsum(vf ** 2)])
    lo = np.maximum(np.arange(n) - w // 2, 0)
    hi = np.minimum(np.arange(n) + w // 2, n)
    cnt = np.maximum(hi - lo, 1)
    s1 = c1[hi] - c1[lo]
    s2 = c2[hi] - c2[lo]
    mu = s1 / cnt
    var = np.maximum(s2 / cnt - mu ** 2, 1e-9)
    return mu.astype(np.float32), np.sqrt(var).astype(np.float32)


def smooth(v, k=9):
    ker = np.ones(k, np.float32) / k
    return np.convolve(v, ker, mode="same")


def runs_of(mask):
    out, i, n = [], 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def close_gaps(mask, hop_s, max_gap):
    m = mask.copy()
    for a, b in runs_of(~m):
        if a == 0 or b == len(m):
            continue
        if (b - a) * hop_s <= max_gap:
            m[a:b] = True
    return m


def open_gaps(mask, hop_s, max_len):
    m = mask.copy()
    for a, b in runs_of(m):
        if (b - a) * hop_s <= max_len:
            m[a:b] = False
    return m


def detect(feat_path, out_json, top_k=400, min_dur=0.7, gate=None, join_gap=1.3):
    f = load(feat_path)
    hop = float(f["hop_s"])
    db, band, flat, cent, zcr, base = (f["db"], f["band"], f["flat"],
                                       f["cent"], f["zcr"], f["base"])
    rise = db - base

    def z(v, win_s):
        mu, sd = rolling_mean_std(v, max(4, int(win_s / hop)))
        return np.clip((v - mu) / (sd + 1e-6), -3, 8).astype(np.float32)

    z_rise = z(rise, 20.0)
    z_db = z(db, 20.0)
    z_band = z(band, 60.0)
    z_flat = z(flat, 60.0)
    z_cent = z(cent, 60.0)
    z_zcr = z(zcr, 60.0)

    score = (0.44 * np.clip(z_rise, 0, None)
             + 0.14 * np.clip(z_db, 0, None)
             + 0.16 * np.clip(z_band, -1, None)
             + 0.10 * np.clip(z_flat, -1, None)
             + 0.09 * np.clip(z_cent, -1, None)
             + 0.07 * np.clip(z_zcr, -1, None))
    score = smooth(score, 7)

    gate = np.percentile(score, 93.0) if gate is None else gate
    mask = score > gate
    mask = close_gaps(mask, hop, 0.5)
    mask = open_gaps(mask, hop, 0.22)
    mask = close_gaps(mask, hop, 0.35)

    evs = runs_of(mask)
    merged = []
    for a, b in evs:
        if merged and (a - merged[-1][1]) * hop < join_gap:
            prev = merged[-1]
            if score[a:b].max() > score[prev[0]:prev[1]].max():
                prev[0], prev[1] = a, b
            else:
                prev[1] = max(prev[1], b)
        else:
            merged.append([a, b])

    res = []
    for a, b in merged:
        d = (b - a) * hop
        if d < min_dur:
            continue
        pk = a + int(np.argmax(score[a:b]))
        res.append(dict(
            start=round(a * hop, 2), end=round(b * hop, 2),
            dur=round(d, 2), peak=round(pk * hop, 2),
            peak_db=round(float(db[pk]), 1),
            rise_db=round(float(np.max(rise[a:b])), 1),
            mean_db=round(float(db[a:b].mean()), 1),
            band=round(float(np.median(band[a:b])), 3),
            flat=round(float(np.median(flat[a:b])), 4),
            cent=round(float(np.median(cent[a:b])), 0),
            score=round(float(score[a:b].max()), 3),
        ))
    res.sort(key=lambda r: -r["score"])
    res = res[:top_k]
    kept = sorted(res, key=lambda r: r["start"])

    out = dict(npz=feat_path, duration=round(float(f["duration"]), 1),
               gate=round(float(gate), 3),
               n_events=len(kept), events=kept)
    with open(out_json, "w") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

    print(f"{feat_path}\n  {out['duration']/60:.1f} min  →  {len(kept)} 个候选事件")
    for r in res[:20]:
        print(f"    {r['start']:8.1f}s +{r['dur']:5.2f}s  峰{r['peak_db']:6.1f}dB "
              f"跃升{r['rise_db']:5.1f} 评分{r['score']:.3f} "
              f"band={r['band']:.2f} cent={r['cent']:.0f}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("npz")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--gate", type=float, default=None,
                    help="score 门槛；不给则用 93 百分位自适应")
    ap.add_argument("--min-dur", type=float, default=0.7)
    a = ap.parse_args()
    detect(a.npz, a.out, gate=a.gate, min_dur=a.min_dur)
