"""Three-in-one character reference node; no online generation or model calls."""
from __future__ import annotations

import hashlib
import json

import numpy as np
import torch
from PIL import Image, ImageOps

from .catalog import (
    DEFAULT_IDS, KINDS, LABELS, MAX_IMAGE_PIXELS, AtlasError,
    catalogue, choose_item, public_item,
)

RESIZE_MODES = ["原始尺寸", "等比留边", "居中裁剪", "拉伸"]
STYLES = {
    "写实人像写真": "写实商业摄影级质感，85mm 人像镜头，自然柔和光影，真实肌肤纹理与织物细节，高清画质。",
    "日系赛璐璐": "精致日系赛璐璐插画，清晰线稿，通透配色，柔和赛璐璐阴影，完整保留服装剪裁与配色。",
    "厚涂插画": "精致厚涂人物插画，自然体积感，细腻材质刻画，统一光影，保留真实服装结构。",
    "水彩插画": "轻柔水彩人物插画，自然留白，柔和色彩晕染，清晰保留人物、穿搭和姿势特征。",
    "无预设": "",
}


def load_image(cat, item, resize_mode: str, width: int, height: int,
               flip: bool = False, variant: str = "original") -> Image.Image:
    if resize_mode not in RESIZE_MODES:
        raise AtlasError("未知图片尺寸处理方式。")
    try:
        with Image.open(cat.path(item, variant)) as opened:
            if opened.width * opened.height > MAX_IMAGE_PIXELS:
                raise AtlasError(f"图片超过3200万像素：{item['id']}")
            image = ImageOps.exif_transpose(opened).convert("RGBA")
            background = Image.new("RGBA", image.size, "white")
            background.alpha_composite(image)
            image = background.convert("RGB")
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise AtlasError(f"图片无法读取或已损坏：{item['id']}") from exc
    if flip:
        image = ImageOps.mirror(image)
    size = (width, height)
    if resize_mode == "等比留边":
        image = ImageOps.pad(image, size, method=Image.Resampling.LANCZOS, color="white")
    elif resize_mode == "居中裁剪":
        image = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
    elif resize_mode == "拉伸":
        image = image.resize(size, Image.Resampling.LANCZOS)
    return image


def tensor(image: Image.Image) -> torch.Tensor:
    return torch.from_numpy(np.asarray(image, dtype=np.float32) / 255.0).unsqueeze(0)


def build_prompt(items: dict[str, dict], style: str) -> str:
    portrait, costume, pose = items["portrait"], items["costume"], items["pose"]
    style_text = STYLES.get(style, "")
    sections = [
        "请结合提供的 3 张参考图，融合成一张完整的人物图像：",
        f"• 【图1（人像参考）】：保持图1人物五官、脸型与气质一致，发型参考「{portrait['title']}」。",
        f"• 【图2（服装参考）】：穿上图2中的完整服饰「{costume['title']}」（{costume['prompt']}），还原面料质感、剪裁、层次与配饰。",
        f"• 【图3（姿势参考）】：身体姿态与镜头透视遵循图3「{pose['title']}」【{pose['angle'] or '参考角度'}】，仅参考骨架动作，忽略素体白模材质。",
    ]
    if style_text:
        sections.append(f"• 【画风要求】：{style_text}")
    sections.append("人物比例协调，手部与五官自然，穿搭完整，光影统一。")
    return "\n".join(sections)


class CharacterAtlas:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "portrait_id": ("STRING", {"default": DEFAULT_IDS["portrait"], "tooltip": "点击「打开三合一图库」选择人像。"}),
            "costume_id": ("STRING", {"default": DEFAULT_IDS["costume"], "tooltip": "点击「打开三合一图库」选择服装。"}),
            "pose_id": ("STRING", {"default": DEFAULT_IDS["pose"], "tooltip": "点击「打开三合一图库」选择姿势。"}),
            "style": (list(STYLES), {"default": "写实人像写真"}),
            "randomize_on_run": ("BOOLEAN", {"default": False, "label_on": "每次按种子随机", "label_off": "使用所选配方"}),
            "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            "resize_mode": (RESIZE_MODES, {"default": "等比留边"}),
            "width": ("INT", {"default": 512, "min": 64, "max": 4096, "step": 8}),
            "height": ("INT", {"default": 768, "min": 64, "max": 4096, "step": 8}),
            "flip_pose": ("BOOLEAN", {"default": False, "label_on": "翻转姿势", "label_off": "不翻转"}),
        }}

    RETURN_TYPES = ("IMAGE", "IMAGE", "IMAGE", "IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("人像图片", "服装图片", "姿势图片", "参考拼图", "组合提示词", "配方JSON")
    FUNCTION = "execute"
    CATEGORY = "ComfyUI_Character-Atlas_ZH/角色三合一图库"
    DESCRIPTION = "整合人像、服装和姿势参考，支持随机配方、参考拼图及组合提示词；不在线生成图片。"

    def execute(self, portrait_id=DEFAULT_IDS["portrait"], costume_id=DEFAULT_IDS["costume"],
                pose_id=DEFAULT_IDS["pose"], style="写实人像写真",
                randomize_on_run=False, seed=0, resize_mode="等比留边", width=512, height=768,
                flip_pose=False):
        ids = {"portrait": portrait_id, "costume": costume_id, "pose": pose_id}
        items = {kind: choose_item(kind, ids[kind], randomize_on_run, seed) for kind in KINDS}
        images = {}
        for kind in KINDS:
            images[kind] = load_image(catalogue(kind), items[kind], resize_mode, width, height,
                                      flip=flip_pose if kind == "pose" else False)
        widths = [image.width for image in images.values()]
        heights = [image.height for image in images.values()]
        separator = 8
        collage = Image.new("RGB", (sum(widths) + separator * 2, max(heights)), "white")
        x = 0
        for kind in KINDS:
            image = images[kind]
            collage.paste(image, (x, (collage.height - image.height) // 2))
            x += image.width + separator
        recipe = {
            "ids": {kind: items[kind]["id"] for kind in KINDS},
            "items": {kind: public_item(items[kind]) for kind in KINDS},
            "style": style, "seed": seed, "randomize_on_run": randomize_on_run,
            "order": ["portrait", "costume", "pose"],
        }
        return (*[tensor(images[kind]) for kind in KINDS], tensor(collage),
                build_prompt(items, style), json.dumps(recipe, ensure_ascii=False, indent=2))

    @classmethod
    def IS_CHANGED(cls, portrait_id=DEFAULT_IDS["portrait"], costume_id=DEFAULT_IDS["costume"],
                   pose_id=DEFAULT_IDS["pose"], style="写实人像写真", randomize_on_run=False, seed=0,
                   resize_mode="等比留边", width=512, height=768, flip_pose=False, **kwargs):
        ids = {"portrait": portrait_id, "costume": costume_id, "pose": pose_id}
        digest = hashlib.sha256()
        digest.update(f"{randomize_on_run}:{seed}:{style}:{resize_mode}:{width}:{height}:{flip_pose}".encode())
        for kind in KINDS:
            cat = catalogue(kind)
            digest.update(cat.fingerprint([] if randomize_on_run else [ids[kind]]).encode())
        return digest.hexdigest()


NODE_CLASS_MAPPINGS = {"CharacterAtlas": CharacterAtlas}
NODE_DISPLAY_NAME_MAPPINGS = {"CharacterAtlas": "角色三合一图库 · 人像/服装/姿势"}
