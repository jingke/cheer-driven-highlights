#!/usr/bin/env python3
"""按 highlights.json 的 candidates（全部、不筛选）切独立片段。

用于用户要求"全剪、不筛选"的场景：把归并后的每个候选都切成 13s 独立片段，
命名 hl{idx}_{grade}_{src}_{goal}s.mp4，按 (src, goal_est) 时间排序。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

FF = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"


def sh(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr[-2000:], file=sys.stderr)
        raise SystemExit(f"ffmpeg failed: {cmd[:80]}")
    return p


def cut_one(src, ss, dur, out, fps=30):
    sh([FF, "-hide_banner", "-nostdin", "-y",
        "-ss", f"{ss:.3f}", "-i", src, "-t", f"{dur:.3f}",
        "-map", "0:v:0", "-map", "0:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-af", f"afade=t=in:st=0:d=0.25,afade=t=out:st={max(0,dur-0.3):.2f}:d=0.3",
        "-movflags", "+faststart", out])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default="work/highlights.json")
    ap.add_argument("--outdir", default="out/clips_all")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    d = json.load(open(a.plan))
    cands = sorted(d["candidates"], key=lambda x: (x["src"], x["goal_est"]))
    parts = []
    for i, c in enumerate(cands, 1):
        out = f"{a.outdir}/hl{i:03d}_{c['grade']}_{c['src']}_{int(c['goal_est'])}s.mp4"
        cut_one(c["src_file"], c["ss"], c["clip_dur"], out)
        parts.append(out)
        c["clip_file"] = os.path.abspath(out)
    json.dump(d, open(a.plan, "w"), ensure_ascii=False, indent=1)
    print(f"完成 {len(parts)} 个片段 → {a.outdir}/")


if __name__ == "__main__":
    main()
