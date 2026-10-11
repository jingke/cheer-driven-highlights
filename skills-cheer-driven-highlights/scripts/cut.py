#!/usr/bin/env python3
"""按清单切独立片段（精选版，读 final.json 的 selected）。

画面：libx264 CRF 20；音频：保留原声 + 头尾淡入淡出（避免切片爆音）。
片段时长 = 前 pre_s + 后 post_s（切点已含回溯）。
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
        print(p.stderr[-3000:], file=sys.stderr)
        raise SystemExit(f"ffmpeg failed: {' '.join(cmd[:6])}...")
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
    ap.add_argument("--plan", default="work/final.json")
    ap.add_argument("--outdir", default="out/clips")
    ap.add_argument("--workdir", default="work")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    d = json.load(open(a.plan))
    sel = d["selected"]
    parts = []
    for i, c in enumerate(sel, 1):
        out = f"{a.outdir}/hl{i:03d}_{c['src']}_{int(c['goal_est'])}s.mp4"
        print(f"[{i}/{len(sel)}] 切 {c['src']} @ {c['ss']:.1f}s +{c['clip_dur']:.1f}s "
              f"爆发{c['n_events']}次 → {os.path.basename(out)}", flush=True)
        cut_one(c["src_file"], c["ss"], c["clip_dur"], out)
        parts.append(out)
        c["clip_file"] = out

    json.dump(d, open(a.plan, "w"), ensure_ascii=False, indent=1)
    with open(f"{a.workdir}/parts.txt", "w") as f:
        f.write("\n".join(parts))
    print(f"\n完成 {len(parts)} 个片段")


if __name__ == "__main__":
    main()
