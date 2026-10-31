"""Unified, read-only access to the pose, costume and portrait libraries."""
from __future__ import annotations

import hashlib
import json
import os
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KINDS = ("portrait", "costume", "pose")
LABELS = {"portrait": "人像", "costume": "服装", "pose": "姿势"}
DEFAULT_IDS = {
    "portrait": "f71f980dde3",
    "costume": "SPR-0001",
    "pose": "full_single_P001_front",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
MAX_IMAGE_PIXELS = 32_000_000


class AtlasError(ValueError):
    """An actionable catalogue or image error."""


def library_root(kind: str) -> Path:
    if kind not in KINDS:
        raise AtlasError(f"未知图库类型：{kind}")
    if kind == "portrait":
        return ROOT / "library"
    if kind == "costume":
        configured = os.environ.get("COMFYUI_COSTUME_GALLERY_ROOT")
        return Path(configured).expanduser() if configured else ROOT.parent / "ComfyUI_Costume-Gallery_ZH"
    configured = os.environ.get("COMFYUI_POSE_GALLERY_LIBRARY")
    return Path(configured).expanduser() if configured else ROOT.parent / "comfyui-pose-gallery" / "library"


def safe_image_path(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise AtlasError("素材路径不能为空。")
    if "\\" in value or value.startswith("/") or re.match(r"^[a-zA-Z]:", value):
        raise AtlasError(f"素材须使用库内相对路径：{value}")
    root = root.resolve()
    path = (root / value).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise AtlasError(f"素材路径不合法：{value}")
    return path


def _text(row: dict, key: str, default: str = "") -> str:
    value = row.get(key, default)
    return value.strip() if isinstance(value, str) else default


def _normalize(kind: str, row: dict) -> dict:
    item_id = _text(row, "id")
    if not item_id:
        raise AtlasError("图库记录缺少 ID。")
    original = _text(row, "原图")
    thumbnail = _text(row, "缩略图", original) or original
    preview = _text(row, "大图", original) or original
    if not original:
        raise AtlasError(f"素材 {item_id} 缺少原图路径。")
    if kind == "costume":
        title = _text(row, "关键词中文", item_id)
        prompt = _text(row, "关键词", title)
        category = _text(row, "分类", "未分类")
        group = "服装穿搭"
        angle = ""
        tags = row.get("标签", [])
        description = title
    elif kind == "pose":
        title = _text(row, "姿势名称", item_id)
        category = _text(row, "分类", "未分类")
        group = _text(row, "体系", "姿势")
        angle = _text(row, "角度")
        prompt = "，".join(value for value in (title, angle) if value)
        tags = [value for value in (group, category, angle) if value]
        description = " / ".join(value for value in (group, category, title, angle) if value)
    else:
        title = _text(row, "标题") or " · ".join(value for value in (_text(row, "发长"), _text(row, "发型名称")) if value) or item_id
        prompt = title
        category = _text(row, "分区", "未分类")
        group = _text(row, "发长", "全部发长")
        angle = ""
        tags = [value for value in (_text(row, "分区"), _text(row, "发长"), _text(row, "发型名称")) if value]
        description = title
    if not isinstance(tags, list):
        tags = []
    tags = list(dict.fromkeys(str(tag) for tag in tags if str(tag).strip()))
    paths = {"original": original, "thumb": thumbnail, "preview": preview}
    if kind == "portrait" and _text(row, "全身图"):
        paths["fullbody"] = _text(row, "全身图")
    search = " ".join([item_id, title, prompt, category, group, angle, _text(row, "检索"), *tags]).lower()
    return {
        "id": item_id, "kind": kind, "title": title, "prompt": prompt,
        "category": category, "group": group, "angle": angle, "tags": tags,
        "description": description, "search": search, "hot": bool(row.get("热门", False)),
        "has_fullbody": "fullbody" in paths, "_paths": paths,
    }


class Catalogue:
    def __init__(self, kind: str, root: Path, signature: tuple):
        self.kind = kind
        self.root = root.resolve()
        self.signature = signature
        filename = "portrait-zh.json" if kind == "portrait" else "costume-zh.json" if kind == "costume" else "pose-zh.json"
        self.catalogue_path = self.root / "data" / filename
        try:
            rows = json.loads(self.catalogue_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise AtlasError(self.missing_message(self.kind)) from exc
        if not isinstance(rows, list) or not rows:
            raise AtlasError(f"{LABELS[kind]}图库清单须为非空数组：{self.catalogue_path}")
        self.items = []
        self.by_id = {}
        for row in rows:
            if not isinstance(row, dict):
                raise AtlasError(f"{LABELS[kind]}图库包含无效记录。")
            item = _normalize(kind, row)
            if item["id"] in self.by_id:
                raise AtlasError(f"{LABELS[kind]}图库 ID 重复：{item['id']}")
            for value in item["_paths"].values():
                safe_image_path(self.root, value)
            self.items.append(item)
            self.by_id[item["id"]] = item
        self.facets = {
            "groups": sorted({item["group"] for item in self.items if item["group"]}),
            "categories": sorted({item["category"] for item in self.items if item["category"]}),
            "angles": sorted({item["angle"] for item in self.items if item["angle"]}),
        }

    @staticmethod
    def missing_message(kind: str) -> str:
        if kind == "portrait":
            return "人像素材未安装：请运行插件 scripts/download_portraits.py 后重启 ComfyUI。"
        name = "ComfyUI_Costume-Gallery_ZH" if kind == "costume" else "comfyui-pose-gallery"
        return f"无法读取{LABELS[kind]}图库，请确认已安装 {name} 且素材完整。"

    def item(self, item_id: str) -> dict:
        try:
            return self.by_id[item_id]
        except (KeyError, TypeError) as exc:
            raise AtlasError(f"{LABELS[self.kind]}图库中找不到 ID「{item_id}」，请重新选择。") from exc

    def path(self, item: dict, variant: str = "original") -> Path:
        if variant not in {"original", "thumb", "preview", "fullbody"}:
            raise AtlasError("未知图片类型。")
        key = variant if variant in item["_paths"] else "original"
        path = safe_image_path(self.root, item["_paths"][key])
        if key != "original" and not path.is_file():
            path = safe_image_path(self.root, item["_paths"]["original"])
        if not path.is_file():
            if self.kind == "portrait":
                raise AtlasError(f"人像图片缺失：{path.name}。请重新运行人像素材下载脚本。")
            raise AtlasError(f"图片文件缺失：{path.name}，请检查素材是否完整。")
        return path

    def fingerprint(self, item_ids: list[str]) -> str:
        parts = [str(self.root), repr(self.signature)]
        for item_id in item_ids:
            item = self.item(item_id)
            stat = self.path(item).stat()
            parts.extend((item["id"], str(stat.st_mtime_ns), str(stat.st_size)))
        return hashlib.sha256("|".join(parts).encode()).hexdigest()


@lru_cache(maxsize=12)
def _cached(kind: str, root: str, signature: tuple) -> Catalogue:
    return Catalogue(kind, Path(root), signature)


def catalogue(kind: str) -> Catalogue:
    root = library_root(kind).resolve()
    filename = "portrait-zh.json" if kind == "portrait" else "costume-zh.json" if kind == "costume" else "pose-zh.json"
    try:
        stat = (root / "data" / filename).stat()
    except OSError as exc:
        raise AtlasError(Catalogue.missing_message(kind)) from exc
    return _cached(kind, str(root), (stat.st_mtime_ns, stat.st_size))


def public_item(item: dict) -> dict:
    return {key: value for key, value in item.items() if not key.startswith("_") and key != "search"}


def choose_item(kind: str, item_id: str, randomize: bool, seed: int) -> dict:
    cat = catalogue(kind)
    if not randomize:
        return cat.item(item_id)
    import random
    return random.Random(f"{seed}:{kind}").choice(cat.items)
