#!/usr/bin/env python3
"""把全部候选合成完整版集锦（不筛选）。

超过 40 段时**分批发**（每批 <=40 段 xfade → 无重编码 concat 拼接），
避免单条 ffmpeg 命令 filtergraph 过长 / 内存过高。分段也有代价：
分批 loudnorm 后拼接会让 True Peak 叠加（可能 >0dBTP），故合成后统一压一次
limiter（视频流 -c copy 直拷，只重编码音频，极快）——见 run_pipeline 的 fix_tp。
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
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]
XD = 0.30
BATCH = 40


def find_font():
    for f in FONTS:
        if os.path.exists(f):
            return f
    return None


def sh(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr[-3000:], file=sys.stderr)
        raise SystemExit("ffmpeg failed")
    return p


def make_card(no, grade, src, goal_est, n_events, out):
    font = find_font()
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


def assemble_batch(parts, cards, out, total_dur):
    n = len(parts)
    inputs, vparts, aparts = [], [], []
    for i in range(n):
        dur = 13.0
        inputs += ["-i", parts[i], "-loop", "1", "-t", "13", "-i", cards[i]]
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
        off = i * 13.0 - XD * i
        lbl = f"[vx{i}]" if i < n - 1 else "[vfinal]"
        f.append(f"{cur}[v{i}o]xfade=transition=fade:duration={XD}:offset={off:.3f}{lbl}")
        cur = lbl
    f += aparts
    cur_a = "[a0]"
    for i in range(1, n):
        lbl = f"[ax{i}]" if i < n - 1 else "[afinal]"
        f.append(f"{cur_a}[a{i}]acrossfade=d={XD}:c1=tri:c2=tri{lbl}")
        cur_a = lbl
    f.append(f"[afinal]loudnorm=I=-16:TP=-1.5:LRA=11,"
             f"afade=t=out:st={max(0,total_dur-1.2):.2f}:d=1.2[aout]")
    f.append("[vfinal]scale=1920:1080,fps=30,format=yuv420p,settb=AVTB[vout]")
    sh([FF, "-hide_banner", "-nostdin", "-y"] + inputs +
       ["-filter_complex", ";".join(f), "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-profile:v", "high", "-level", "4.1", "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000", "-maxrate", "10M", "-bufsize", "20M",
        "-movflags", "+faststart", out])


def fix_true_peak(infile, outfile):
    """视频 -c copy 直拷，仅重编码音频加 limiter，把 TP 压到 <0，极快。"""
    sh([FF, "-hide_banner", "-nostdin", "-y", "-i", infile,
        "-map", "0:v", "-map", "0:a", "-c:v", "copy",
        "-af", "alimiter=limit=0.97:level=disabled:attack=5:release=80",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", outfile])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default="work/highlights.json")
    ap.add_argument("--out", default="out/全集.mp4")
    a = ap.parse_args()
    os.makedirs("work/cards_all", exist_ok=True)
    d = json.load(open(a.plan))
    cands = sorted(d["candidates"], key=lambda x: (x["src"], x["goal_est"]))
    parts, cards = [], []
    for i, c in enumerate(cands, 1):
        parts.append(c["clip_file"])
        cp = f"work/cards_all/card{i:03d}.png"
        make_card(i, c["grade"], c["src"], c["goal_est"], c["n_events"], cp)
        cards.append(cp)

    batches = [cands[i:i + BATCH] for i in range(0, len(cands), BATCH)]
    pfiles, idx0 = [], 0
    for bi, b in enumerate(batches, 1):
        bp = parts[idx0:idx0 + len(b)]
        bc = cards[idx0:idx0 + len(b)]
        pf = f"work/part{bi}.mp4"
        bdur = len(b) * 13.0 - XD * (len(b) - 1)
        print(f"[批 {bi}/{len(batches)}] 合成 {len(b)} 段 → {pf}", flush=True)
        assemble_batch(bp, bc, pf, bdur)
        pfiles.append(pf)
        idx0 += len(b)

    with open("work/concat.txt", "w") as fh:
        fh.write("\n".join(f"file '{os.path.abspath(p)}'" for p in pfiles))
    tmp = "work/_all_tmp.mp4"
    sh([FF, "-hide_banner", "-nostdin", "-y", "-f", "concat", "-safe", "0",
        "-i", "work/concat.txt", "-c", "copy", tmp])
    fix_true_peak(tmp, a.out)
    print("输出:", a.out)


if __name__ == "__main__":
    main()
