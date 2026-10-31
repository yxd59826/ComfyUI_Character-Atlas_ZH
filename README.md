# ComfyUI Character Atlas ZH（角色三合一图库）

将 **人像 + 服装 + 姿势** 三类参考整合到一个 ComfyUI 节点。适合 AI 穿搭分享、人像生成和角色配方整理；节点不调用在线生图 API。

## 功能

- 三个图库页签：人像 1,499 张、服装 1,407 套、姿势 1,439 张（数量随原插件素材更新）。
- 中文/英文/ID 搜索，按体系、分类、发长和视角筛选。
- 单库随机、整套随机；也可开启“每次按种子随机”，同一种子可复现。
- 输出三张独立 `IMAGE`、三合一参考拼图、结构化组合提示词和配方 JSON。
- 支持原始尺寸、等比留边、居中裁剪、拉伸及姿势水平翻转。
- 素材和选图均在本地执行，不需要 API Key。

## 节点使用

1. 重启 ComfyUI 并刷新浏览器，搜索节点 **「角色三合一图库 · 人像/服装/姿势」**。
2. 点击节点上的 **「打开三合一图库」**，分别在三个页签中选图；点击「随机整套」可快速生成配方。
3. 按需连接输出：
   - `人像图片`：人物身份、五官及发型参考。
   - `服装图片`：穿搭与面料参考。
   - `姿势图片`：可连接 Depth Anything、姿势编辑或其他图像条件节点。
   - `参考拼图`：按人像、服装、姿势从左到右排列。
   - `组合提示词`：可连接文本编码或反推/润色节点。
   - `配方JSON`：保存实际选中 ID 与完整素材信息；随机模式下记录本次实际结果。
4. 默认关闭 `randomize_on_run`，使用图库选中的固定 ID。开启后按 `seed` 从完整三库随机；图库筛选不会影响节点执行时的随机范围。

节点只提供参考和提示词，后续生成连接现有 MOSS、Qwen、Flux 等工作流即可。

## 素材结构

服装和姿势不重复复制，直接读取已安装的同级插件：

```text
F:\ComfyUI\custom_nodes\
├── ComfyUI_Character-Atlas_ZH\
├── ComfyUI_Costume-Gallery_ZH\
└── comfyui-pose-gallery\
```

人像素材位于本插件 `library/`，已经通过公开中文仓库下载。以后补全或修复人像素材可运行：

```powershell
& 'F:\ComfyUI\.venv\Scripts\python.exe' 'F:\ComfyUI\custom_nodes\ComfyUI_Character-Atlas_ZH\scripts\download_portraits.py' --workers 16
```

脚本会跳过已有文件，支持中断后继续。也可设置 `COMFYUI_COSTUME_GALLERY_ROOT` 和 `COMFYUI_POSE_GALLERY_LIBRARY` 环境变量指定服装插件根目录及姿势库目录。

## 与 ControlNet 配合

姿势图输出的是人体结构参考，需要由 ControlNet 这类适配器来约束生成：

- MOSS 工作流要额外加载 `moss_image_color_depth_control.safetensors`（放入 `ComfyUI/models/loras/`，用 `LoraLoaderModelOnly` 接在主模型链上，强度 1.0）。
- `MOSSImageControl` 只负责把深度图编码进条件，本身不含 ControlNet 权重；`strength` 建议 1.0、`start_percent` 0、`end_percent` 1.0。
- 普通 SD/Flux 工作流则接对应的 ControlNet（depth/openpose）节点。

## 示例工作流

`examples/` 里有五个已实测跑通的工作流，复制到 `F:\ComfyUI\user\default\workflows\` 即可打开：

| 文件 | 用途 | 需要模型 |
| --- | --- | --- |
| `01_只看参考_零依赖.json` | 只看三张参考图 + 拼图 + 提示词，不加载任何模型 | 无 |
| `02_Qwen-Image-2.1_三图融合.json` | 人像/服装/姿势分别接 `TextEncodeQwenImage21` 的 image_1/2/3，真融合出图 | Qwen-Image 2.1（UNet + qwen3vl + vae） |
| `03_MOSS_人像肌感_深度控制.json` | 姿势图走 Depth Anything V2 → `MOSSImageControl`，复刻人像肌感主链（只有姿势生效） | MOSS base+sft、两个 LoRA、Depth Anything V2 |
| `04_MOSS_编辑版_人脸加服装.json` | 人像/服装/姿势进 `TextEncodeMOSSImageEdit`（Picture 1/2/3），走官方 edit LoRA | 03 的模型 + `moss_image_edit_lora_rank_64_bf16` |
| `05_Krea2_换装_保脸最稳.json` | `Krea2 Identity Edit v1.2` try-on，人像 + 服装两张参考，**保脸最稳** | krea2_turbo、qwen3vl_4b、qwen_image_vae、`krea2_identity_edit_v1_2` |

保脸实测（同一测试条件下 insightface 余弦相似度）：Krea2 **0.458** > Qwen 0.347 ≫ MOSS 0.07。
明细见 `examples/README.md`（含模型清单、调参提示和验证记录）。

## 更新记录

- 1.0.3：新增示例 04（MOSS 编辑版，人像/服装/姿势进 `TextEncodeMOSSImageEdit`）和 05（Krea2 Identity Edit 换装）；补保脸实测对比（Krea2 0.458 / Qwen 0.347 / MOSS 0.07）；示例全部在本机 8188 实跑 `status success`。
- 1.0.2：新增 `examples/` 三个示例工作流（零依赖预览、Qwen-Image 2.1 三图融合、MOSS 深度控制），均已在本机 8188 实测 `status success`。
- 1.0.1：修正 `IS_CHANGED` 未跟踪尺寸、画风、翻转等参数导致改参数后命中缓存的问题；隐藏按钮和预览控件不再写入工作流 `widgets_values`；移除无效的“人像视图”选项（公开人像库没有全身图数据）。

## 验证

```powershell
& 'F:\ComfyUI\.venv\Scripts\python.exe' -m unittest discover -s 'F:\ComfyUI\custom_nodes\ComfyUI_Character-Atlas_ZH\tests' -v
```

## 来源与许可

- 界面与功能参考：[Anhao AI 角色三合一参考台](https://ai-pose-gallery.anhao.app/costumes)及其[公开仓库](https://github.com/anhao/ai-pose-gallery-zh)。
- 人像中文索引与图片来自上述公开仓库；姿势、服装使用本机两个插件的已有素材。
- 图片及原始数据权利属于原作者 ギア（@giaaibusi），不适用本插件代码的 MIT 许可；请遵守原素材条款。本插件新增代码采用 MIT，见 `LICENSE`。
