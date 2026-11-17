# 实测踩坑清单（全部来自真实运行）

## 1. 内存爆炸：整体读 WAV
`np.frombuffer(wave.readframes(n))` 整体读 140MB WAV + 建 `(n_frames,1024)`
索引矩阵 → 2.8GB → **SIGTERM**。
**修**：`feats.py` 流式分块（chunk=60s）+ `as_strided` 零拷贝；特征数组极小。

## 2. 特征归一化：固定阈值全部失效
拍脑袋设 `band>0.35`、`flat>0.02` 等绝对阈值 → 0 检出（实测分布远低于假设）。
**修**：局部 z-score（累积和滚动均值/方差）。详见 algorithm.md §3。

## 3. xfade filtergraph 输出未连接
把 `filters.append(";".join(vparts))` 放进循环内，绕出重复链导致
`Filter has output unconnected`。
**修**：`vparts`/`aparts` 只在循环**外**整体 append 一次；循环内只追加链式 xfade。

## 4. 大批量合成：单条命令过载
120 段 xfade（240 inputs + 巨长 filtergraph）单条 ffmpeg 易慢/不稳。
**修**：`assemble_all.py` 分批（每批 ≤40 段）→ 各 `work/partN.mp4`
→ `concat` demuxer `-c copy` 无重编码拼接。

## 5. 响度 True Peak 叠加超 0
分批各自 `loudnorm I=-16 TP=-1.5` 后拼接，整体 True Peak 实测 **+0.8 dBTP**（削波风险）。
**修**：合成后统一压一次 —— 视频 `-c copy` 直拷，仅重编码音频加
`alimiter=limit=0.97:level=disabled`。极快（25min 音频 ~1min），TP 降到 -0.2。

## 6. PIL 渐变负底数 → complex 报错
`int(215*(1 - i/(W*0.72))**1.5)`，i 超过 W*0.72 时底数为负 → complex。
**修**：clamp `lim = int(W*0.72)`，只对 `range(lim)` 画。

## 7. 字体 / ffmpeg 硬编码路径不可移植
`/System/Library/Fonts/STHeiti Medium.ttc`、`/opt/homebrew/bin/ffmpeg` 写死
→ 换平台即崩。
**修**：`find_font()` 探测多平台中文字体列表；`FF = os.environ.get("FFMPEG")
or shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"`。

## 8. 大素材不要全量抽帧
素材 ≥2GB 或 ≥300s 时，全量解码数十分钟且易超时。本流程**不依赖画面分析**
（欢呼声驱动），只随机点抽帧做二次确认（`-ss` 随机寻址抽帧 0.2~0.3s）。

## 9. 画面限制：无法区分进球 vs 失误
固定机位远景、人物极小、无观众特写时，只能定位「何时欢呼」，
**无法从画面判断是进球还是错失机会**。交付时务必提示人工过一遍确认性质。

## 10. 本清单的维护约定（经验回写）

新坑追加为下一编号条目，沿用「现象 → 实测数值 / 报错 → **修**：」三段式。
- **证据**：必须带具体命令、量化数值或退出码，不写「可能是」「感觉」。
- **闸门**：可复现、有证据、不与既有条目冲突；单次观测标注「待复现」，
  ≥2 次复现才升级为 `SKILL.md` / `goal-review.md` 里的规则。
- **收尾**：改动后跑 `package_skill.py` 重打包，并同步 repo 副本；
  专家包改动另需 `validate_expert.py` + `register_expert.py`。
- 提交与推送须用户明确确认，不自动执行。每周由定时自动化蒸馏 daily log
  （见专家 MD「经验回写协议」）。

## 11. 球门后机位：静止球检测（三帧求交）失效

`check_goal.py` 依赖"固定机位下球门/草坪静止、进球后球静止在网内"。
**球门后机位（网在前景、镜头朝场内）下此前提失效**：网后球员持续活动，
实测 `thr=25` 时网内框中位噪声 2493 px（俯拍机位接近 0），无法区分球与人。
**修**：此类机位放弃 check_goal.py，改密集时间窗（8fps）亮斑检测 + 原分辨率目检。

## 12. 连通域批量检测触发 SIGTERM + 全片扫描成本失控

- 对 2360 帧逐帧 `scipy.ndimage.label` 连通域 → 内存/时间超限，Exit 137 SIGTERM。
  **修**：改纯 numpy 小尺寸（300×168）向量化统计 `m.sum()` / `roi.max()`，
  单候选 40 帧仅 8MB，稳定通过。
- 全片 4fps 抽帧（87min → 21k 帧 ≈ 840MB / >6min 未完成）代价过高。
  **修**：只对音频候选 ±2s 开密集窗（59×40=2360 帧 / 2min），收益更高。

## 13. 开场黑帧导致 Finder 缩略图全黑（交付前必查 t=0）

`assemble*.py` 的合成链把 `fade=t=in:st=0:d=0.2` 加在**视频层** →
第 0 帧 mean=0.0（纯黑），0.05s 才 mean=37.5，0.2s 全亮。
macOS Finder / 预览面板取**第 0 帧**生成缩略图，于是封面显示全黑，
用户会误以为成片损坏；短视频预览面板同样受影响。

**修（双层，都做最稳）**：
1. **治本**：去掉视频层开场淡入（`fade=t=in:st=0:d=0.2,settb=AVTB[v{i}o]`
   → `settb=AVTB[v{i}o]`），重合成。字幕卡自身的 `fade=t=in:st=0:d=0.25`
   叠加在已有画面上，不会造成黑场，无需动。
   实测修复后 t=0 mean=0.0 → **91.5**、亮像素 94.4%。
2. **加固**：抽 t=0.3s 帧作封面，用 `-c copy` 嵌 attached_pic：
   `ffmpeg -i V.mp4 -i cover.jpg -map 0 -map 1 -c copy -disposition:v:1 attached_pic -movflags +faststart OUT.mp4`
   验证封面流 `attached_pic=1`、主视频流仍 `default=1`，播放解码不受影响。

**交付前自检**：`ffmpeg -ss 0 -frames:v 1` 抽第 0 帧算 mean，**<10 即判开场黑**，
必须修复后再交付。`qlmanage -t` 在本沙箱报 `sandbox initialization failed:
Operation not permitted`，无法强制刷新 Finder 缓存，但非黑首帧 + attached_pic 已足够。

