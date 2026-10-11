#!/usr/bin/env python3
"""强档筛选：从归并候选里挑「真事件」。

判据（足球/演出声学经验，可调）：
  total_cheer >= 6s  —— 真事件引发**持续**多轮欢呼；口哨/碰撞只是一声
  n_events >= 3      —— 连续爆发次数（单次爆响多为口哨/误报）
  band >= 0.70        —— 宽频=人群欢呼；窄带(<0.5)多为哨声/单人喊
  goal_est >= 15s    —— 排除素材开头（摄像机开机/风声）
  同源 ±20s 内取最强的一处（避免一次事件被切多段）

不筛选模式（--top 0 或不调用本脚本）即取全部候选，见 cut_all.py。
"""
import argparse
import json

TOT_CHEER_MIN = 6.0
N_EVENTS_MIN = 3
BAND_MIN = 0.70
HEAD_SKIP = 15.0


def select(cands, top=10):
    pool = [c for c in cands
            if c["total_cheer"] >= TOT_CHEER_MIN
            and c["n_events"] >= N_EVENTS_MIN
            and c["band"] >= BAND_MIN
            and c["goal_est"] >= HEAD_SKIP]
    pool.sort(key=lambda c: -c["rank"])
    picked = []
    for c in pool:
        clash = any(p["src"] == c["src"]
                    and abs(p["goal_est"] - c["goal_est"]) < 20.0
                    for p in picked)
        if clash:
            continue
        picked.append(c)
        if top and len(picked) >= top:
            break
    return sorted(picked, key=lambda c: (c["src"], c["goal_est"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--in", default="work/highlights.json")
    ap.add_argument("--top", type=int, default=10,
                    help="保留前 N 个最强（按 rank）。0 = 不限制数量，只按判据筛")
    ap.add_argument("-o", "--out", default="work/final.json")
    a = ap.parse_args()
    d = json.load(open(a.i))
    sel = select(d["candidates"], a.top)
    json.dump(dict(criteria=dict(total_cheer_min=TOT_CHEER_MIN,
                                n_events_min=N_EVENTS_MIN,
                                band_min=BAND_MIN, head_skip=HEAD_SKIP),
                   pre_s=d["pre_s"], post_s=d["post_s"],
                   selected=sel), open(a.out, "w"),
              ensure_ascii=False, indent=1)
    print(f"最终选中 {len(sel)} 个片段")
    tot = sum(c["clip_dur"] for c in sel)
    print(f"总时长 {tot:.0f}s = {tot/60:.1f} min\n")
    for i, c in enumerate(sel, 1):
        print(f"{i:>3} {c['src']:<10} {c['goal_est']:8.1f}s "
              f"{c['ss']:7.1f}-{c['end_t']:7.1f}s 爆发{c['n_events']:>3} "
              f"欢呼{c['total_cheer']:>4.1f}s 评分{c['score']:>5.2f} band{c['band']:.2f}")
