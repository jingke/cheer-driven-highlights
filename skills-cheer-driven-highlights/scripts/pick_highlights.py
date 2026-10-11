#!/usr/bin/env python3
"""把候选欢呼事件归并成「事件候选」，并输出剪辑清单。

一次进球/一次精彩扑救/一次爆笑，常引发**连续多轮**欢呼（第一声 + 持续爆发 +
尾声），检测器会把它们切成多个事件。同一次事件的多个爆发间隔通常 <25s，
且越往后能量越弱；相邻的两次独立事件（快攻、换人）可能间隔仅 10~20s。
归并阈值取 22s：合并同一事件的连响，又不把两次独立事件粘一起。

完全通用：源视频路径通过 --video-dir 自动匹配，不写死任何具体文件。
"""
import argparse
import json
import os

import numpy as np


def group_events(events, hop=0.02, join_s=22.0):
    evs = sorted(events, key=lambda e: e["start"])
    groups, cur = [], []
    for e in evs:
        if cur and (e["start"] - cur[-1]["end"]) > join_s:
            groups.append(cur)
            cur = []
        cur.append(e)
    if cur:
        groups.append(cur)

    out = []
    for g in groups:
        top = max(g, key=lambda e: e["score"])
        start = min(e["start"] for e in g)
        end = max(e["end"] for e in g)
        onset = min(g, key=lambda e: e["start"])
        out.append(dict(
            gstart=round(start, 2), gend=round(end, 2),
            cheer_onset=round(onset["peak"], 2),
            # 事件瞬间估计：首个爆发峰值再往前 0.8s（人耳反应延迟）
            goal_est=round(max(0.0, onset["peak"] - 0.8), 2),
            n_events=len(g),
            score=round(top["score"], 3),
            peak_db=round(top["peak_db"], 1),
            rise_db=round(top["rise_db"], 1),
            total_cheer=round(sum(e["dur"] for e in g), 2),
            band=round(float(np.median([e["band"] for e in g])), 3),
        ))
    return out


def classify(c):
    s = c["score"]
    multi = min(c["n_events"], 4) / 4.0          # 连续多轮爆发 → 像真事件
    wide = min(max(c["band"], 0.0), 1.0)         # 宽频=人群欢呼
    rank = s + 0.55 * multi + 0.30 * wide
    return dict(rank=round(rank, 3),
                grade=("S" if rank >= 3.4 else
                       "A" if rank >= 3.0 else
                       "B" if rank >= 2.7 else "C"))


def find_video(vdir, base):
    for ext in (".MP4", ".mp4", ".MOV", ".mov", ".mkv", ".avi", ".MOV"):
        p = os.path.join(vdir, base + ext)
        if os.path.exists(p):
            return p
    for f in os.listdir(vdir):
        if base in f and f.lower().endswith((".mp4", ".mov", ".mkv", ".avi")):
            return os.path.join(vdir, f)
    return None


def build(events_dir, video_dir, pre_s=5.0, post_s=8.0):
    ev_files = sorted(__import__("glob").glob(os.path.join(events_dir, "*_events.json")))
    if not ev_files:
        raise SystemExit(f"没找到事件 json：{events_dir}/*_events.json")
    all_c = []
    for ef in ev_files:
        base = os.path.basename(ef).replace("_events.json", "")
        src_file = find_video(video_dir, base)
        if not src_file:
            print(f"  [跳过] 找不到源视频匹配 {base!r}（在 {video_dir}）")
            continue
        d = json.load(open(ef))
        evs = [e for e in d["events"] if e["dur"] >= 0.5]
        for c in group_events(evs):
            c["src"] = base
            c["src_file"] = src_file
            c.update(classify(c))
            ss = max(0.0, c["goal_est"] - pre_s)
            dur = pre_s + post_s
            if ss + dur > d["duration"]:
                dur = max(3.0, d["duration"] - ss)
            c["ss"] = round(ss, 2)
            c["clip_dur"] = round(dur, 2)
            c["end_t"] = round(ss + dur, 2)
            all_c.append(c)
    all_c.sort(key=lambda c: -c["rank"])
    return all_c


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--events-dir", default="work")
    ap.add_argument("--video-dir", required=True,
                    help="源视频所在目录（按文件名前缀自动匹配 events json）")
    ap.add_argument("--pre", type=float, default=5.0)
    ap.add_argument("--post", type=float, default=8.0)
    ap.add_argument("--min-grade", default="B")
    ap.add_argument("-o", "--out", default="work/highlights.json")
    a = ap.parse_args()
    order = {"S": 3, "A": 2, "B": 1, "C": 0}
    cands = build(a.events_dir, a.video_dir, a.pre, a.post)
    keep = [c for c in cands if order[c["grade"]] >= order[a.min_grade]]
    json.dump(dict(pre_s=a.pre, post_s=a.post, total=len(keep),
                   candidates=cands, selected=keep),
              open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"归并后候选 {len(cands)} 个→ 选中 {len(keep)} 个 (grade>={a.min_grade})")
    for i, c in enumerate(keep, 1):
        print(f"{i:>3} {c['grade']:<4} {c['src']:<10} {c['goal_est']:8.1f}s "
              f"{c['ss']:7.1f}-{c['end_t']:7.1f}s 爆发{c['n_events']:>3} "
              f"欢呼{c['total_cheer']:>4.1f}s 评分{c['score']:>5.2f} band{c['band']:.2f}")
