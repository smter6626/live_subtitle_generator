import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import build_app_icon as app_icon  # noqa: E402


MANIFEST_PATH = REPO_ROOT / "packaging" / "runtime_manifest.json"


class AppIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.contract = app_icon.contract_from_manifest(cls.manifest)

    def test_manifest_owns_a_portable_tracked_source(self):
        raw = self.manifest["frozen"]["app_icon"]
        for key in (
            "source_path",
            "generation_script_path",
            "generated_icns_path",
            "bundle_target",
        ):
            with self.subTest(key=key):
                path = PurePosixPath(raw[key])
                self.assertFalse(path.is_absolute())
                self.assertNotIn("..", path.parts)
        self.assertTrue(raw["required"])
        self.assertEqual(raw["bundle_filename"], "ClassroomTranscriber.icns")
        self.assertTrue(self.contract.source_path.is_file())
        self.assertEqual(
            hashlib.sha256(self.contract.source_path.read_bytes()).hexdigest(),
            raw["source_sha256"],
        )
        self.assertNotIn(
            "/Users/",
            (SCRIPTS_DIR / "build_app_icon.py").read_text(encoding="utf-8"),
        )

    def test_source_normalizes_to_a_transparent_1024px_master(self):
        source = app_icon.load_source_image(self.contract)
        self.assertFalse(source.hasAlphaChannel())
        master = app_icon.render_master_icon(source)
        self.assertEqual((master.width(), master.height()), (1024, 1024))
        self.assertTrue(master.hasAlphaChannel())
        for x, y in ((0, 0), (1023, 0), (0, 1023), (1023, 1023)):
            with self.subTest(point=(x, y)):
                self.assertEqual(master.pixelColor(x, y).alpha(), 0)
        self.assertEqual(master.pixelColor(512, 512).alpha(), 255)

    def test_generator_emits_a_structurally_valid_icns(self):
        source = app_icon.load_source_image(self.contract)
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / self.contract.bundle_filename
            app_icon.generate_icns(source, destination)
            app_icon.verify_icns(destination)
            header = destination.read_bytes()[:8]
            self.assertEqual(header[:4], b"icns")
            self.assertEqual(int.from_bytes(header[4:], "big"), destination.stat().st_size)


if __name__ == "__main__":
    unittest.main()
