#!/usr/bin/env python3
"""Sync, validate, and reproducibly package the standalone skill as a plugin."""

import argparse
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "things"
SKILL_FILES = (
    "SKILL.md", "agents/openai.yaml", "scripts/things.py",
    "scripts/things.js", "scripts/check_setup.sh",
)
COPIES = {name: "skills/things/" + name for name in SKILL_FILES}
COPIES.update({"LICENSE": "LICENSE", "PRIVACY.md": "PRIVACY.md"})
PACKAGE_FILES = tuple(sorted((
    "plugin.json", "README.md", "assets/icon.svg",
    "skills/things-setup/SKILL.md", "skills/things-setup/agents/openai.yaml",
    *COPIES.values(),
)))


def sync():
    for source, destination in COPIES.items():
        target = PLUGIN / destination
        if target.is_symlink() or any(parent.is_symlink() for parent in target.parents):
            raise ValueError("Refusing to write through a symlink: " + destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / source).read_bytes())


def check():
    for name in PACKAGE_FILES:
        path = PLUGIN / name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(PLUGIN.resolve()):
            raise ValueError("Missing or unsafe package file: " + name)
    for source, destination in COPIES.items():
        if (ROOT / source).read_bytes() != (PLUGIN / destination).read_bytes():
            raise ValueError("Plugin copy is stale; run --sync: " + destination)

    manifest = json.loads((PLUGIN / "plugin.json").read_text())
    if manifest.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json":
        raise ValueError("Use the portable Agent Plugins manifest schema.")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", manifest.get("name", "")):
        raise ValueError("Invalid plugin name.")
    if len(manifest["name"]) > 64 or not re.fullmatch(r"\d+\.\d+\.\d+", manifest.get("version", "")):
        raise ValueError("Provide a valid name and release version.")
    extension = manifest["extensions"]["com.openai"]
    interface = extension["interface"]
    for field, maximum in (("displayName", 30), ("shortDescription", 30), ("longDescription", 4000), ("developerName", 80)):
        value = interface.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError("Missing or overlong listing field: " + field)
    prompts = interface.get("defaultPrompt", [])
    if not isinstance(prompts, list) or len(prompts) > 3 or any(not isinstance(p, str) or not p.strip() or len(p) > 128 for p in prompts):
        raise ValueError("Provide up to three starter prompts, each at most 128 characters.")
    for path in (extension["onboardingSkill"], interface["logo"], interface["composerIcon"]):
        if not path.startswith("./") or path[2:] not in PACKAGE_FILES:
            raise ValueError("Manifest references an unpackaged file: " + path)
    for name, skill in (("things", "skills/things/SKILL.md"), ("things-setup", "skills/things-setup/SKILL.md")):
        contents = (PLUGIN / skill).read_text()
        if not contents.startswith("---\nname: " + name + "\ndescription: "):
            raise ValueError("Invalid skill metadata: " + skill)
    svg = ET.fromstring((PLUGIN / interface["logo"][2:]).read_text())
    viewbox = [float(value) for value in svg.attrib["viewBox"].split()]
    if viewbox[2] != viewbox[3] or viewbox[2] < 48:
        raise ValueError("The icon must be square and at least 48 by 48.")
    return manifest


def build(output_dir):
    manifest = check()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / (manifest["name"] + "-" + manifest["version"] + ".zip")
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in PACKAGE_FILES:
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (PLUGIN / name).read_bytes())
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync", action="store_true", help="Update the committed plugin copies from the standalone skill")
    parser.add_argument("--check", action="store_true", help="Check package contents and listing constraints (always run)")
    parser.add_argument("--output-dir", type=Path, help="Also write a submission ZIP in this directory")
    args = parser.parse_args()
    try:
        if args.sync:
            sync()
        manifest = check()
        print("Validated " + manifest["name"] + " " + manifest["version"])
        if args.output_dir:
            print(build(args.output_dir))
        return 0
    except (ValueError, KeyError, OSError, ET.ParseError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
