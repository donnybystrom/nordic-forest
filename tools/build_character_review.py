"""Install the data-driven character reviewer in the existing Godot project.

Each additional GLB must have its own directory: Godot extracts embedded textures
with material-derived names, which otherwise collide between characters.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "output/zombie-beach/rodin-tpose-v1/godot-review"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(catalog_path, project):
    catalog = json.loads(catalog_path.read_text())
    assert catalog["schema_version"] == 1
    entries = catalog["characters"]
    assert entries and len({c["id"] for c in entries}) == len(entries)
    assert all(c["scene"].startswith("res://") and c["scene"].endswith(".glb") for c in entries)
    assert len({str(Path(c["scene"][6:]).parent) for c in entries}) == len(entries), "Separate texture directories required"
    manifest = json.loads((ROOT / catalog["motion_manifest"]).read_text())
    sources = [(entry, ROOT / entry["source"]) for entry in entries]
    assert all(source.is_file() for _, source in sources)
    project.mkdir(parents=True, exist_ok=True)
    for entry, source in sources:
        relative = Path(entry["scene"].removeprefix("res://"))
        assert not relative.is_absolute() and ".." not in relative.parts
        target = project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        entry["sha256"] = digest(source)
        if not target.exists() or digest(target) != entry["sha256"]:
            shutil.copyfile(source, target)
        # Godot generates the full .import file; the advanced override preserves
        # sampled reference keys rather than simplifying extremal joint poses.
        override = target.with_suffix(target.suffix + ".import")
        text = override.read_text() if override.exists() else "[remap]\nimporter=\"scene\"\n\n[params]\n"
        settings = '_subresources={"nodes": {"PATH:AnimationPlayer": {"optimizer/enabled": false, "compression/enabled": false}}}'
        lines = text.splitlines()
        existing = next((i for i, line in enumerate(lines) if line.startswith("_subresources=")), None)
        if existing is not None:
            # Godot serializes dictionaries over multiple lines. Remove through
            # their closing brace before installing the complete override.
            stop = existing + 1
            balance = lines[existing].count("{") - lines[existing].count("}")
            while balance > 0 and stop < len(lines):
                balance += lines[stop].count("{") - lines[stop].count("}")
                stop += 1
            lines[existing:stop] = [settings]
        else:
            lines.append(settings)
        updated = "\n".join(lines) + "\n"
        if not override.exists() or override.read_text() != updated:
            override.write_text(updated)
    catalog["clips"] = manifest["clips"]
    (project / "characters.json").write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")
    for source in (ROOT / "integrations/godot/character-review").iterdir():
        if source.suffix in {".gd", ".tscn", ".godot"}:
            target = project / source.name
            if not target.exists() or digest(source) != digest(target):
                shutil.copyfile(source, target)
    print(json.dumps({"project": str(project), "characters": len(entries), "shared_clips": len(catalog["clips"])}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "config/character-review-catalog.json")
    parser.add_argument("--project", type=Path, default=PROJECT)
    args = parser.parse_args()
    build(args.catalog, args.project)
