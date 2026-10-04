"""Validate the shipped plugin and exercise its extracted helper."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("package_plugin", ROOT / "scripts" / "package_plugin.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


class PackageTests(unittest.TestCase):
    def test_plugin_and_standalone_skill_are_in_sync(self):
        manifest = package.check()
        self.assertEqual(manifest["name"], "things-macos")

    def test_marketplace_resolves_to_the_packaged_plugin(self):
        market = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
        entry, = market["plugins"]
        self.assertEqual((ROOT / entry["source"]["path"]).resolve(), package.PLUGIN)
        self.assertEqual(entry["name"], package.check()["name"])

    def test_archive_is_reproducible_and_contains_only_release_files(self):
        with tempfile.TemporaryDirectory() as directory:
            first = package.build(Path(directory) / "one").read_bytes()
            second = package.build(Path(directory) / "two")
            self.assertEqual(first, second.read_bytes())
            with zipfile.ZipFile(second) as archive:
                self.assertEqual(archive.namelist(), list(package.PACKAGE_FILES))
                self.assertIsNone(archive.testzip())
                self.assertNotIn(".git", archive.namelist())
                self.assertNotIn("tests/test_cli.py", archive.namelist())

    def test_extracted_skill_runs_outside_the_repository(self):
        with tempfile.TemporaryDirectory(prefix="things plugin ") as directory:
            directory = Path(directory)
            archive_path = package.build(directory)
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(directory / "installed")
            helper = directory / "installed/skills/things/scripts/things.py"
            result = subprocess.run(
                [sys.executable, str(helper), "request", "--validate-only"],
                input='{"op":"create","title":"Synthetic task","when":"tomorrow"}',
                cwd=directory, text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["validated"])
            self.assertFalse(json.loads(result.stdout)["connected"])
