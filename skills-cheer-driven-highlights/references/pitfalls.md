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
