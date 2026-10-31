# 示例工作流

五个可直接双击打开的 ComfyUI 工作流，覆盖「只想看参考」到「真正出图、还要保脸」的几种用法。
都只依赖本插件 + 你本机已有的模型，不联网、不调用任何在线 API。

导入方式：把本目录里的 `.json` 复制到 `F:\ComfyUI\user\default\workflows\`，
然后在 ComfyUI 侧栏的 **工作流** 列表里点开即可（安装脚本已经把五份都拷贝进去了，
文件名前缀 `CharacterAtlas示例_`）。

**先看结论：想要脸像，用 `05`（Krea2 Identity Edit）；想要姿势准，用 `04`（MOSS 编辑版）；
`02` 是折中、也是唯一三张参考图全进模型的方案。**

---

## 01 只看参考（零依赖，不加载模型）

`01_只看参考_零依赖.json`

8 个节点，2 秒出结果，不需要任何模型文件。

- 节点输出：人像 / 服装 / 姿势三张图 + 一张参考拼图 + 组合提示词 + 配方 JSON。
- 右边四个 `PreviewImage` 分别是三张参考和拼图；两个 `PreviewAny` 显示提示词与配方。
- 用来确认图库素材、所选配方、随机换装是否符合预期，再拿去接自己的工作流。

## 02 Qwen-Image 2.1 三图融合

`02_Qwen-Image-2.1_三图融合.json`

真正使用三张参考图：`TextEncodeQwenImage21` 的 `images.image_1/2/3` 分别接
人像、服装、姿势，`prompt` 接组合提示词（里面自带「图1/图2/图3」的角色说明）。

用到的模型（本机已装）：

| 位置 | 文件 |
| --- | --- |
| `diffusion_models` | `qwen_image_2.1_bf16.safetensors` |
| `text_encoders` | `qwen3vl_8b_bf16.safetensors`（type = `qwen_image`） |
| `vae` | `qwen_image_2.1_vae_bf16.safetensors` |

`QwenImage21Cache` + `TESpeedQwenImage21` 是加速节点，删掉也能跑，只是慢一点。

调参提示：

- 画面比例由 `resolution` 控制（1024 ≈ 1024² 面积），节点上的 `width/height`
  影响的是三张参考图本身，两者不必严格一致。
- 脸不像 → 换更清晰的正脸人像，或把人像图放在 `image_1`。
- 衣服换不动 → 把服装描述提到组合提示词最前面。

## 03 MOSS 人像肌感 + 姿势深度控制

`03_MOSS_人像肌感_深度控制.json`

复刻 `MOSS｜真实感暴击 · 人像肌感` 的主链，把三个输入换成本节点的输出：

```text
姿势图片 → DepthAnythingV2Preprocessor → MOSSImageControl.depth_map
组合提示词 → CLIPTextEncode → MOSSImageControl.positive
人像图片 / 服装图片 → 通过组合提示词里的描述文字生效
```

模型链：`moss_image_base_bf16 + moss_image_sft_bf16 → MOSSMergePreset(Balanced 0.45)`
→ `moss\moss_image_color_depth_control`（强度 1.0）→ `moss\KOOK-MOSS-SFT-观澜`（0.9）
→ `SkipLayerGuidanceDiTSimple` → KSampler（er_sde / 25 步 / cfg 3.5）。

注意：MOSS 是文生图模型，**参考图只通过深度图和提示词起作用**，它并不真的"看"人像图和
服装图——这就是"只有姿势、没有脸和衣服"的原因。要真正用上三张参考，用 02 或 04。

- 深度图尺寸跟姿势图一致（节点已经把姿势图缩放到 `width × height`）。
  只有 `EmptyFlux2LatentImage` 的尺寸是手填的，换尺寸时记得一起改。
- `MOSSImageControl` 的 `strength` 给到 1.1、`start/end = 0/1`：姿势约束全程生效。
  觉得画面太"僵"就往 0.7~0.9 降。
- VOSR2 放大那条线没带上，需要的话从原来的 MOSS 工作流里拷过来接在 `VAEDecode` 后面。

## 04 MOSS 编辑版：真的看人脸 + 衣服

`04_MOSS_编辑版_人脸加服装.json`

03 只有姿势，是因为 MOSS 的 color/depth 控制适配器里 `color_map` 是「每个区域一个纯色」
的区块图（颜色只是区域编号），塞照片进去也传不了长相和服装。这一版改走官方的
edit LoRA 路径：

```text
人像图片 → Picture 1     服装图片 → Picture 2     姿势图片 → Picture 3
        ↓
TextEncodeMOSSImageEdit（Qwen3.5-VL 真的“看”这三张图）
        ↓
CLIPTextEncode 的 prompt 接「组合提示词」（里面自带 图1 保五官 / 图2 换装 / 图3 跟姿势）
        ↓
moss_image_edit_lora_rank_64_bf16 → KSampler
姿势另走 Depth Anything V2 → MOSSImageControl.depth_map 再钉一遍骨架
```

额外需要的模型（283 MB，官方仓库）：

```text
https://huggingface.co/Comfy-Org/MOSS-Image/resolve/main/loras/moss_image_edit_lora_rank_64_bf16.safetensors
→ F:\models\Lora\moss\moss_image_edit_lora_rank_64_bf16.safetensors
```

调参提示：

- 觉得脸还是不像：`TextEncodeMOSSImageEdit` 的 `image_strength` 从 `1.0` 提到 `1.3~1.6`。
- 觉得画面僵：`MOSSImageControl` 的 `strength` 从 `1.0` 降到 `0.7`。
- `images` 的插槽是从 `image_0` 开始编号的（不是 `image_1`），接错会报 `required_input_missing`。

## 05 Krea2 换装：保脸最稳（推荐）

`05_Krea2_换装_保脸最稳.json`

`Krea 2 Identity Edit v1.2` 官方就支持 **try-on / 换头换衣**，靠 `ref_boost` 调“像不像”。
本 demo 用两张参考图：`人像图片` → image 1 / `source_image`（决定长相、发型、身材），
`服装图片` → image 2 / `source_image_b`（决定穿什么）。

```text
krea2_turbo_fp8_scaled
  → krea2_identity_edit_v1_2（LoRA）
  → Krea2EditModelPatch（source_image / source_image_b + ref_boost）
  → KSampler（8 步、cfg 1、euler/simple）
```

用到的模型（本机已装）：

| 位置 | 文件 |
| --- | --- |
| `diffusion_models` | `krea2_turbo_fp8_scaled.safetensors` |
| `text_encoders` | `qwen3vl_4b_fp8_scaled.safetensors`（type = `krea2`） |
| `vae` | `qwen_image_vae.safetensors` |
| `loras/krea2` | `krea2_identity_edit_v1_2.safetensors` |

调参提示：

- `ref_boost` 默认 4，官方建议 2~6。越高越像参考图，过高会僵、甚至直接“贴图”。
- 服装不听话：在正向指令里把衣服写具体（颜色 / 材质 / 版型 / 长度）。指令故意写成英文，
  Krea2 的 edit 分支以英文语料训练，中文能跑但稳定性差一点。
- 脸不像：换更清晰的正脸人像，或把 `服装图片` 撤掉只留一张参考。
- 姿势：Krea2 这一版不吃第三张参考图，姿势来自 `source_image`（人像图）本身。
  要严格按姿势图摆动作，用 04 的 MOSS 深度控制，或先按姿势图生成再换脸。

---

## 保脸效果实测对比

同一个测试条件（人像 `f71f980dde3`、服装 `SPR-0001`、姿势 `full_single_P001_front`、
768×1024 全身图），用 `insightface buffalo_l` 算生成脸与参考人像的余弦相似度（同一个人一般 ≥ 0.3）：

| 工作流 | 人像相似度 | 说明 |
| --- | --- | --- |
| 05 Krea2 Identity Edit | **0.458** | 明显高于阈值，脸基本对得上 |
| 02 Qwen-Image 2.1 | 0.347 | 能看出是同一个人，细节会漂 |
| 03 MOSS 深度控制 | 0.078 | 等于没吃到人像 |
| 04 MOSS 编辑版 | 0.069 | 图进了模型，但长相没跟过来 |

生成图里脸只有 80~90 像素宽（全身构图），这个尺寸下 0.45 已经是相当强的同一性。
另外单独验证过：只换参考图、提示词和种子都不动，输出会明显变化（同一输入两次跑字节完全一致），
说明参考图确实进了采样，不是摆设。

---

## 验证记录

五份示例都在 `F:\ComfyUI`（8188）上实际提交 `/prompt` 跑通：

| 工作流 | 结果 |
| --- | --- |
| 01 | `status success`，4 张预览 + 2 段文本 |
| 02 | `status success`，出图 `output/CharacterAtlas/三合一融合_00001_.png`（测试时 steps 降到 8、resolution 降到 768） |
| 03 | `status success`，出图 `output/CharacterAtlas/MOSS_肌感_00001_.png`（steps 8 快速验证） |
| 04 | `status success`，139 s，出图 `output/CharacterAtlas/MOSS_编辑版_00001_.png` |
| 05 | `status success`，244 s，出图 `output/CharacterAtlas/Krea2_换装_00001_.png` |

正式出图把 steps 改回默认即可（02 是 30 步，03 是 25 步，04 是 25 步，05 是 8 步 turbo）。