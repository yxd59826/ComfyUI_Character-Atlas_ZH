# 示例工作流

三个可直接双击打开的 ComfyUI 工作流，覆盖「只想看参考」到「真正出图」的三种用法。
都只依赖本插件 + 你本机已有的模型，不联网、不调用任何在线 API。

导入方式：把本目录里的 `.json` 复制到 `F:\ComfyUI\user\default\workflows\`，
然后在 ComfyUI 侧栏的 **工作流** 列表里点开即可（安装脚本已经把三份拷贝进去了，
文件名前缀 `CharacterAtlas示例_`）。

---

## 01 只看参考（零依赖，不加载模型）

`01_只看参考_零依赖.json`

8 个节点，2 秒出结果，不需要任何模型文件。

- 节点输出：人像 / 服装 / 姿势三张图 + 一张参考拼图 + 组合提示词 + 配方 JSON。
- 右边四个 `PreviewImage` 分别是三张参考和拼图；两个 `PreviewAny` 显示提示词与配方。
- 用来确认图库素材、所选配方、随机换装是否符合预期，再拿去接自己的工作流。

## 02 Qwen-Image 2.1 三图融合（推荐出图用）

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
服装图。要真正用上三张参考，用 02 的 Qwen 版本。

- 深度图尺寸跟姿势图一致（节点已经把姿势图缩放到 `width × height`）。
  只有 `EmptyFlux2LatentImage` 的尺寸是手填的，换尺寸时记得一起改。
- `MOSSImageControl` 的 `strength` 给到 1.1、`start/end = 0/1`：姿势约束全程生效。
  觉得画面太"僵"就往 0.7~0.9 降。
- VOSR2 放大那条线没带上，需要的话从原来的 MOSS 工作流里拷过来接在 `VAEDecode` 后面。

---

## 验证记录

三份示例都在 `F:\ComfyUI`（8188）上实际跑通：

| 工作流 | 结果 |
| --- | --- |
| 01 | `status success`，4 张预览 + 2 段文本 |
| 02 | `status success`，出图 1 张（测试时把 steps 降到 8、resolution 降到 768） |
| 03 | `status success`，出图 `output/CharacterAtlas/MOSS_肌感_00001_.png`（steps 8 快速验证） |

正式出图把 steps 改回默认即可（02 是 30 步，03 是 25 步）。