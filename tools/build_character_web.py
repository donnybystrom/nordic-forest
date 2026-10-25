"""Export the tracked two-character lab without local generation jobs or Blender.

The reviewed runtime GLBs and catalog are checked in. Only these assets and the
authored Godot scripts enter the temporary project; build/ remains Git-ignored.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "output/zombie-beach/rodin-tpose-v1/godot-review"
AUTHORED = ROOT / "integrations/godot/character-review"
DEFAULT_BUILD = ROOT / "build/character-web"
RUNTIME_FILES = ("review.gd", "active_ragdoll.gd", "physical_pose.gd", "web_status.gd", "review.tscn", "project.godot", "entry.gd", "entry.tscn")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(destination, clean_site=True):
    project, site = destination / "project", destination / "site"
    project.mkdir(parents=True, exist_ok=True)
    # A failed export must not leave old payloads in a new deployment.
    if clean_site and site.exists():
        shutil.rmtree(site)
    site.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((RUNTIME / "characters.json").read_text())
    assert catalog["schema_version"] == 1 and catalog["characters"]
    verified = []
    allowed_scenes = set()
    for entry in catalog["characters"]:
        assert entry["scene"].startswith("res://")
        relative = Path(entry["scene"].removeprefix("res://"))
        assert relative.suffix == ".glb" and not relative.is_absolute() and ".." not in relative.parts
        source = RUNTIME / relative
        assert sha(source) == entry["sha256"], f"Unreviewed asset change: {source}"
        target = project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or sha(target) != entry["sha256"]:
            shutil.copyfile(source, target)
        allowed_scenes.add(target.resolve())
        # Keep the reference animation keys; extract textures inside each model's
        # own directory to avoid collisions between their material names.
        override = target.with_suffix(".glb.import")
        if not override.exists():
            override.write_text('[remap]\nimporter="scene"\n\n[params]\n_subresources={"nodes":{"PATH:AnimationPlayer":{"optimizer/enabled":false,"compression/enabled":false}}}\n')
        verified.append({"id":entry["id"], "sha256":entry["sha256"], "bytes":source.stat().st_size})
        entry.pop("source", None)
    # Remove retired GLBs on incremental builds so they cannot enter the pack.
    for previous in project.rglob("*.glb"):
        if previous.resolve() not in allowed_scenes:
            previous.unlink()
            previous.with_suffix(".glb.import").unlink(missing_ok=True)
    catalog.pop("motion_manifest", None)
    catalog["default_character"] = "beach-tourist-male"
    (project / "characters.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
    for name in RUNTIME_FILES:
        shutil.copyfile(AUTHORED / name, project / name)
    arena = project / "testground"
    arena.mkdir(exist_ok=True)
    for source in (ROOT / "integrations/godot/testground").iterdir():
        if source.suffix in {".gd", ".tscn", ".tres"}:
            shutil.copyfile(source, arena / source.name)
    shutil.copyfile(ROOT / "integrations/godot/web/shell.html", project / "web-shell.html")
    shutil.copyfile(ROOT / "integrations/godot/web/export_presets.cfg", project / "export_presets.cfg")
    return project, site, verified


def run(engine, project, arguments, log):
    command = [engine, "--headless", "--path", str(project), "--log-file", str(log), *arguments]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    # Godot can return success after a GDScript parse/compile failure.
    if result.returncode or "SCRIPT ERROR:" in result.stdout or "ERROR:" in result.stdout:
        print(result.stdout, file=sys.stderr)
        raise RuntimeError(f"Godot failed; see {log}")
    print(result.stdout[-2500:])


def build(destination, engine, prepare_only=False):
    destination = destination.resolve()
    assert destination != ROOT and ROOT not in destination.parents or destination.is_relative_to(ROOT / "build"), "Use a build output directory"
    project, site, assets = prepare(destination, clean_site=not prepare_only)
    if prepare_only:
        return {"project":str(project), "site":str(site), "assets":assets}
    version = subprocess.check_output([engine, "--version"], text=True).strip()
    assert version.startswith("4.7.1."), f"Expected pinned Godot 4.7.1, got {version}"
    run(engine, project, ["--editor", "--import"], destination / "import.log")
    run(engine, project, ["--script", "res://testground/bake_damage.gd"], destination / "fracture-bake.log")
    run(engine, project, ["--export-release", "Web", str(site / "index.html")], destination / "export.log")
    required = [site / ("index" + suffix) for suffix in (".html", ".js", ".wasm", ".pck")]
    assert all(p.is_file() and p.stat().st_size > 0 for p in required)
    assert not any(p.name.endswith((".blend", ".glb", ".py", ".key")) for p in site.rglob("*"))
    (site / ".nojekyll").write_text("")
    revision = os.environ.get("GITHUB_SHA") or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    report = {"godot":version, "revision":revision, "characters":len(assets), "assets":assets,
              "thread_support":False, "physics_backend":"Jolt Physics",
              "files":[{"name":p.name,"bytes":p.stat().st_size,"sha256":sha(p)} for p in sorted(site.iterdir()) if p.is_file()]}
    (site / "build.json").write_text(json.dumps(report, indent=2) + "\n")
    (destination / "build-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"site":str(site), "bytes":sum(p.stat().st_size for p in site.iterdir() if p.is_file()), "characters":len(assets)}, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_BUILD)
    parser.add_argument("--godot", default=shutil.which("godot") or "godot")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    build(args.output, args.godot, args.prepare_only)
