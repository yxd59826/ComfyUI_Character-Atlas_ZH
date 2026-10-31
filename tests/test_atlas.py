from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_plugin():
    class Routes:
        def get(self, _path):
            return lambda function: function
    server = types.ModuleType("server")
    server.PromptServer = type("PromptServer", (), {"instance": type("Instance", (), {"routes": Routes()})()})
    sys.modules.setdefault("server", server)
    spec = importlib.util.spec_from_file_location("character_atlas_test", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AtlasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()
        cls.catalog = importlib.import_module("character_atlas_test.catalog")
        cls.nodes = importlib.import_module("character_atlas_test.nodes")

    def test_catalogues_and_defaults(self):
        expected = {"portrait": 1499, "costume": 1400, "pose": 1400}
        for kind, minimum in expected.items():
            with self.subTest(kind=kind):
                cat = self.catalog.catalogue(kind)
                self.assertGreaterEqual(len(cat.items), minimum)
                item = cat.item(self.catalog.DEFAULT_IDS[kind])
                self.assertTrue(cat.path(item).is_file())
                self.assertNotIn("_paths", self.catalog.public_item(item))

    def test_portrait_assets_complete(self):
        cat = self.catalog.catalogue("portrait")
        for item in cat.items:
            self.assertTrue(cat.path(item).is_file(), item["id"])
            self.assertTrue(cat.path(item, "thumb").is_file(), item["id"])

    def test_node_outputs_and_prompt(self):
        result = self.nodes.CharacterAtlas().execute()
        self.assertEqual(len(result), 6)
        for image in result[:3]:
            self.assertEqual(tuple(image.shape), (1, 768, 512, 3))
        self.assertEqual(tuple(result[3].shape), (1, 768, 1552, 3))
        self.assertIn("SPR-0001", result[5])
        self.assertIn("人像参考", result[4])
        self.assertIn("ivory", result[4])
        recipe = json.loads(result[5])
        self.assertEqual(recipe["order"], ["portrait", "costume", "pose"])

    def test_random_recipe_is_deterministic(self):
        node = self.nodes.CharacterAtlas()
        first = node.execute(randomize_on_run=True, seed=20261031, width=64, height=64)
        second = node.execute(randomize_on_run=True, seed=20261031, width=64, height=64)
        self.assertEqual(first[5], second[5])
        self.assertTrue(all(item["id"] for item in json.loads(first[5])["items"].values()))

    def test_resize_modes_and_flip(self):
        node = self.nodes.CharacterAtlas()
        for mode in self.nodes.RESIZE_MODES:
            with self.subTest(mode=mode):
                result = node.execute(resize_mode=mode, width=96, height=128, flip_pose=True)
                if mode == "原始尺寸":
                    widths = [image.shape[2] for image in result[:3]]
                    heights = [image.shape[1] for image in result[:3]]
                    self.assertEqual(tuple(result[3].shape), (1, max(heights), sum(widths) + 16, 3))
                    continue
                for image in result[:3]:
                    self.assertEqual(tuple(image.shape), (1, 128, 96, 3))
                self.assertEqual(tuple(result[3].shape), (1, 128, 96 * 3 + 16, 3))
        self.assertNotEqual(node.execute(flip_pose=False)[2].numpy().tobytes(),
                            node.execute(flip_pose=True)[2].numpy().tobytes())

    def test_node_schema_matches_widgets(self):
        required = self.nodes.CharacterAtlas.INPUT_TYPES()["required"]
        self.assertNotIn("portrait_view", required)
        self.assertEqual(
            [name for name in required if name not in {"portrait_id", "costume_id", "pose_id"}],
            ["style", "randomize_on_run", "seed", "resize_mode", "width", "height", "flip_pose"],
        )
        self.assertEqual(len(self.nodes.CharacterAtlas.RETURN_TYPES), 6)

    def test_cache_key_tracks_every_visual_input(self):
        node = self.nodes.CharacterAtlas()
        baseline = node.IS_CHANGED()
        variants = [
            {"width": 768}, {"height": 512}, {"flip_pose": True},
            {"resize_mode": "居中裁剪"}, {"style": "日系赛璐璐"}, {"seed": 1},
            {"randomize_on_run": True}, {"costume_id": "SPR-0002"},
        ]
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertNotEqual(node.IS_CHANGED(**variant), baseline)
        self.assertEqual(node.IS_CHANGED(), baseline)

    def test_path_boundaries(self):
        root = self.catalog.ROOT
        for value in ("../outside.png", "C:/outside.png", "/outside.png", "folder\\outside.png"):
            with self.subTest(value=value), self.assertRaises(self.catalog.AtlasError):
                self.catalog.safe_image_path(root, value)


if __name__ == "__main__":
    unittest.main()
