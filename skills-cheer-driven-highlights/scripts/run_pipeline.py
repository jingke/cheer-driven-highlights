#!/usr/bin/env python3
"""端到端编排：探测素材 → 提音频 → 检测 → 归并 → 切片段 → 合成集锦。

用法：
  python run_pipeline.py <VIDEO_DIR> [--work WORK] [--out OUT]
      [--mode top|all] [--top N] [--pre 5] [--post 8]
      [--dry-run]            # 只跑到候选清单，人工确认后再切
      [--skip-extract]       # 已有 workdir 下的 wav/npz 时跳过提取

流程：
  1. 探测 VIDEO_DIR 下所有视频（扩展名见 VIDEO_EXTS）
  2. 逐视频：提取 16k 单声道 WAV → feats.py 流式特征 → detect2.py 事件
  3. pick_highlights.py：按 22s 归并候选 + 自动匹配源视频路径
  4. 模式：
     top  : final_pick.py 按判据筛强档 → cut.py + assemble.py → 精选集锦
     all  : cut_all.py + assemble_all.py → 完整全集（含分批与 TP 修复）
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO_EXTS = (".mp4", ".MP4", ".mov", ".MOV", ".mkv", ".avi", ".MP4",
              ".m4v", ".MP4")


def py():
    return sys.executable


def set_ffmpeg():
    ff = (os.environ.get("FFMPEG") or shutil.which("ffmpeg")
          or "/opt/homebrew/bin/ffmpeg")
    os.environ["FFMPEG"] = ff
    return ff


def run(script, args, cwd):
    cmd = [py(), os.path.join(HERE, script)] + args
    p = subprocess.run(cmd, cwd=cwd)
    if p.returncode != 0:
        raise SystemExit(f"{script} 失败: {' '.join(args[:4])} ...")


def list_videos(vdir):
    if os.path.isfile(vdir):
        return [vdir]
    vs = []
    for f in sorted(os.listdir(vdir)):
        if f.lower().endswith(VIDEO_EXTS):
            vs.append(os.path.join(vdir, f))
    return vs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_dir")
    ap.add_argument("--work", default="./cheer_work")
    ap.add_argument("--out", default="./cheer_out")
    ap.add_argument("--mode", choices=["top", "all"], default="top")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--pre", type=float, default=5.0)
    ap.add_argument("--post", type=float, default=8.0)
    ap.add_argument("--dry-run", action="store_true",
                    help="只产生候选清单，不切片段")
    ap.add_argument("--skip-extract", action="store_true")
    a = ap.parse_args()

    ff = set_ffmpeg()
    print(f"ffmpeg: {ff}")
    work = os.path.abspath(a.work)
    out = os.path.abspath(a.out)
    os.makedirs(work, exist_ok=True)
    os.makedirs(out, exist_ok=True)

    vdir_abs = os.path.abspath(a.video_dir)
    videos = list_videos(vdir_abs)
    if not videos:
        raise SystemExit(f"在 {a.video_dir} 没找到视频文件")
    # pick_highlights 用 video-dir 匹配源视频，单文件时退回父目录
    video_dir_for_match = (os.path.dirname(vdir_abs)
                           if os.path.isfile(vdir_abs) else vdir_abs)
    print(f"找到 {len(videos)} 个视频")

    # 1) 提取音频 + 特征 + 检测
    for v in videos:
        base = os.path.splitext(os.path.basename(v))[0]
        wav = os.path.join(work, f"{base}.wav")
        npz = os.path.join(work, f"{base}_feats.npz")
        evt = os.path.join(work, f"{base}_events.json")
        if not a.skip_extract or not os.path.exists(npz):
            print(f"[音频] {base}", flush=True)
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "feats", os.path.join(HERE, "feats.py"))
            feats = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(feats)
            feats.extract_audio(v, wav, ffmpeg=ff)
        if not os.path.exists(npz):
            run("feats.py", [wav, "-o", npz], cwd=work)
        if not os.path.exists(evt):
            run("detect2.py", [npz, "-o", evt], cwd=work)

    # 2) 归并候选
    highlights = os.path.join(work, "highlights.json")
    run("pick_highlights.py",
        ["--events-dir", work,
         "--video-dir", video_dir_for_match,
         "--pre", str(a.pre), "--post", str(a.post),
         "-o", highlights], cwd=work)
    d = json.load(open(highlights))
    print(f"\n候选共 {len(d['candidates'])} 个 → "
          f"{a.video_dir} 下素材的欢呼事件分布见候选清单")

    if a.dry_run:
        print("\n[dry-run] 已生成候选清单，未切片段。")
        print(f"  人工确认后可：python run_pipeline.py {a.video_dir} "
              f"--mode {'all' if a.mode=='all' else 'top'} "
              f"--skip-extract --work {a.work} --out {a.out}")
        return

    # 3) 模式分支
    if a.mode == "all":
        clips = os.path.join(out, "clips_all")
        os.makedirs(clips, exist_ok=True)
        run("cut_all.py", ["--plan", highlights, "--outdir", clips], cwd=work)
        final_vid = os.path.join(out, "全集.mp4")
        run("assemble_all.py", ["--plan", highlights, "--out", final_vid], cwd=work)
        print(f"\n完成：全集 {final_vid}（{len(d['candidates'])} 段）")
    else:
        final = os.path.join(work, "final.json")
        run("final_pick.py", ["-i", highlights, "--top", str(a.top),
                               "-o", final], cwd=work)
        sel = json.load(open(final))["selected"]
        clips = os.path.join(out, "clips")
        os.makedirs(clips, exist_ok=True)
        run("cut.py", ["--plan", final, "--outdir", clips], cwd=work)
        final_vid = os.path.join(out, "高光集.mp4")
        run("assemble.py", ["--plan", final, "--out", final_vid], cwd=work)
        print(f"\n完成：精选集 {final_vid}（{len(sel)} 段）")


if __name__ == "__main__":
    main()
