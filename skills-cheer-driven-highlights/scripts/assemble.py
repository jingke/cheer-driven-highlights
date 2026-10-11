#!/usr/bin/env python3
"""把精选片段合成为集锦：转场 + 字幕卡 + 响度归一。

字幕卡：每段开头 3.5s 显示「序号 + 视频名 + 时段 + 爆发次数」，PIL 渲染 RGBA
透明层后 overlay（绕过 ffmpeg 缺 libass 的限制）。3.5s 后自动淡出不挡画面。
转场：0.3s 交叉溶解（xfade）+ 音频 acrossfade。
响度：全片 loudnorm 到 -16 LUFS（现场声场景）。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

FF = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
W, H = 1920, 1080
FONTS = [
    "/System/Library/Fonts/STHeiti Medium.ttc",     # macOS 中文
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",  # Linux 中文
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]


def find_font():
    for f in FONTS:
        if os.path.exists(f):
            return f
    return None


def sh(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr[-4000:], file=sys.stderr)
        raise SystemExit("ffmpeg failed")
    return p


def make_card(no, src, goal_est, n_events, grade, out):
    font = find_font()
    if font is None:
        print("  [警告] 未找到中文字体，字幕可能显示为方块", file=sys.stderr)
    f1 = ImageFont.truetype(font, 76) if font else ImageFont.load_default()
    f2 = ImageFont.truetype(font, 40) if font else ImageFont.load_default()
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(300):
        y = H - 300 + i
        d.line([(0, y), (W, y)], fill=(0, 0, 0, int(200 * (1 - i / 300) ** 1.6)))
    d.rectangle([120, H - 250, 132, H - 130], fill=(255, 45, 45, 255))
    m, s = divmod(int(goal_est), 60)
    d.text((160, H - 262), f"高光 {no:03d}", font=f1, fill=(255, 255, 255, 255))
    d.text((162, H - 168), f"{src} · {m:02d}:{s:02d} · 爆发 {n_events} 次 · {grade}级",
           font=f2, fill=(255, 175, 175, 235))
    img.save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default="work/final.json")
    ap.add_argument("--out", default="out/高光集.mp4")
    a = ap.parse_args()
    os.makedirs("work/cards", exist_ok=True)
    os.makedirs("out", exist_ok=True)

    d = json.load(open(a.plan))
    sel = d["selected"]
    n = len(sel)
    xd = 0.30

    cards = []
    for i, c in enumerate(sel, 1):
        p = f"work/cards/card{i:03d}.png"
        make_card(i, c["src"], c["goal_est"], c["n_events"], c["grade"], p)
        cards.append(p)

    inputs, vparts, aparts = [], [], []
    for i, c in enumerate(sel):
        inputs += ["-i", c["clip_file"], "-loop", "1", "-t", "13", "-i", cards[i]]
        dur = float(c["clip_dur"])
        vparts.append(
            f"[{2*i}:v]trim=0:{dur},setpts=PTS-STARTPTS[v{i}];"
            f"[{2*i+1}:v]trim=0:13,setpts=PTS-STARTPTS,format=rgba,"
            f"fade=t=in:st=0:d=0.25,fade=t=out:st=3.2:d=0.3[c{i}];"
            f"[v{i}][c{i}]overlay=0:0:enable='between(t,0,3.5)',"
            f"fade=t=in:st=0:d=0.2,settb=AVTB[v{i}o]")
        aparts.append(
            f"[{2*i}:a]aformat=sample_fmts=fltp:sample_rates=48000:"
            f"channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}]")

    f = list(vparts)
    cur = "[v0o]"
    for i in range(1, n):
        off = i * 13.0 - xd * i
        lbl = f"[vx{i}]" if i < n - 1 else "[vfinal]"
        f.append(f"{cur}[v{i}o]xfade=transition=fade:duration={xd}:offset={off:.3f}{lbl}")
        cur = lbl
    f += aparts
    cur_a = "[a0]"
    for i in range(1, n):
        lbl = f"[ax{i}]" if i < n - 1 else "[afinal]"
        f.append(f"{cur_a}[a{i}]acrossfade=d={xd}:c1=tri:c2=tri{lbl}")
        cur_a = lbl
    total_dur = n * 13.0 - xd * (n - 1)
    f.append(f"[afinal]loudnorm=I=-16:TP=-1.5:LRA=11,"
             f"afade=t=out:st={max(0,total_dur-1.5):.2f}:d=1.5[aout]")
    f.append("[vfinal]scale=1920:1080,fps=30,format=yuv420p,settb=AVTB[vout]")

    sh([FF, "-hide_banner", "-nostdin", "-y"] + inputs +
       ["-filter_complex", ";".join(f), "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-profile:v", "high", "-level", "4.1", "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000", "-maxrate", "10M", "-bufsize", "20M",
        "-movflags", "+faststart", a.out])
    print("输出:", a.out)


if __name__ == "__main__":
    main()
