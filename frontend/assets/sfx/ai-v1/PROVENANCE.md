# ai-v1 · 来源与许可登记

**5 套打字音效，用本机 Stable Audio 3 生成**（不是第三方素材站，没有作者署名要求）。

## 生成方式

| 项 | 内容 |
|---|---|
| 模型 | Stability AI **Stable Audio 3** · `--dit sm-sfx` + `--decoder same-s`（MLX optimized 路径） |
| 运行位置 | `/Volumes/WorkDisk/AI-Audio/`，Apple M3 Pro / 18GB，单条实测 4~8 秒、峰值内存 1.62GB |
| 入口 | `/Volumes/WorkDisk/AI-Audio/生成音效.command "<英文描述>"` → 5 秒 WAV 落 `outputs/sfx/` |
| 后处理 | `/tmp/build-sfx.py`：按包络手裁瞬态 → 升余弦首尾淡化 → **按 RMS 归一**（普通键 −27 dBFS、重键 −24）→ 单声道 44.1kHz PCM16 |
| 生成日期 | 2026-09-28 |

## 许可：Stability AI Community License

官方条款（https://stability.ai/license ，2026-09-28 查）：

- **允许商用** —— "allows for research, non-commercial, and commercial use"。
- **有营收门槛** —— 年营收 **超过 100 万美元** 的主体需要注册并改用付费的 Enterprise License；
  低于该门槛 "don't need to pay to use or distribute the Core Models"。
  对个人创作者明确写了 "No you won't need to pay — create away!"。
- **生成物的版权归属该页未明确定义** —— 它讲的是模型使用权，没有逐条说明 audio output 的版权归谁。
  这一条我没有证据，不替 Stability 说话。

**对本产品的意义**：当前规模远低于 1M 美元门槛，可以直接用。
**但要在营收接近门槛之前重新评估**，届时要么买 Enterprise，要么把这批换成自建/买断素材。

代码仓库 `stable-audio-3/LICENSE` 是 MIT 文本，但仓库 README 的 License 段写的是
"Please refer to the Stability AI Community License" —— **以社区许可为准**，别把 MIT 当成权重的许可。

## 五套的构成

| 菜单 | 文件 | 说明 |
|---|---|---|
| 💧 水滴 | `drop-normal` / `drop-heavy` | heavy 多留了水波尾巴，更"咚" |
| 🎵 音符 | `note-normal` / `note-heavy` | 八音盒单音；变速会改音高，所以抖动只给 ±6% |
| 🀄 闷麻将 | `mahjong-1/2/3` + `mahjong-heavy` | 源素材里有三次独立咔哒，直接当三个变体轮替，连打不会机关枪 |
| 😋 吞咽 | `swallow-1/2/3/4` | **按顺序轮播**（引擎 `cycle:true`），连打四下拼出完整一口；变速收到 ±2% 以免相位被拉歪 |
| 👾 像素音 | `pixel-normal` / `pixel-heavy` | 8bit 方波 blip |

## 已知问题（还没人耳验过）

1. **没有人工听审。** 我只验到"能解码、时长对、RMS 对齐、信噪比够"（麻将放大 5~10 倍后信噪比仍有 32dB）。
2. **麻将那套原始素材很轻**（源峰值 RMS 只有 0.021），归一时放大了 5.3~10 倍，
   `mahjong-heavy` 撞到了我设的 10 倍上限。听感上如果发虚，应该重生成一条更响的而不是继续加增益。
3. **吞咽的"连打拼一口"依赖顺序播放**，但引擎的声部冷却是 44ms；如果打得极快，
   120ms 的片段会叠在一起，四段就糊成一团。真听感要试。

## 本地 Web 回车水滴变种（2026-09-28）
`drop-enter.wav` 由同目录 `drop-normal.wav` 降调并叠加一颗较轻的延迟水滴制成；未混入机械按键采样。
