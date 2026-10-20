import argparse
import asyncio
import importlib.metadata
import json
from datetime import datetime, timezone

from .workflow import ROOT, load_config, prepare, reserve_run_dir, run_live, save_packet


def main():
    parser = argparse.ArgumentParser(description="Nordic Forest planning harness (offline by default)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    for name in ("assets-fetch", "assets-agent"):
        assets = sub.add_parser(name)
        assets.add_argument("--uid", action="append", required=True)
        assets.add_argument("--format", choices=["source", "glb", "gltf"], action="append", dest="formats")
        assets.add_argument("--sketchfab-token-file")
        if name == "assets-agent":
            assets.add_argument("--live", action="store_true")
            assets.add_argument("--key-file")
            assets.add_argument("--out")
    plan = sub.add_parser("plan")
    plan.add_argument("--request-file", default=str(ROOT / "examples/first-request.txt"))
    plan.add_argument("--specialist", action="append", default=[])
    plan.add_argument("--use-platform-settings", action="store_true")
    plan.add_argument("--reasoning", choices=["low", "medium", "high", "xhigh", "max"],
                      help="Explicit run-only override of saved role reasoning settings")
    plan.add_argument("--live", action="store_true", help="Make billed model calls; otherwise prepare offline")
    plan.add_argument("--key-file", help="Read key in memory only during a live run")
    plan.add_argument("--out", help="New subdirectory under runs/")
    args = parser.parse_args()
    if args.command in {"assets-fetch", "assets-agent"}:
        from .sketchfab_assets import SketchfabCollector
        formats = args.formats or ["source"]
        try:
            if len(set(args.uid)) != len(args.uid) or len(set(formats)) != len(formats) or len(args.uid) * len(formats) > 4:
                raise ValueError("Use unique UID/format pairs, at most four archives")
            if args.command == "assets-fetch":
                collector = SketchfabCollector(args.uid, token_file=args.sketchfab_token_file, allowed_formats=formats)
                for uid in args.uid:
                    for fmt in formats:
                        print(f"Fetching {uid} ({fmt})", flush=True)
                        print(json.dumps(collector.fetch(uid, fmt)), flush=True)
            elif not args.live:
                print(json.dumps({"status": "prepared_offline", "scope": "asset_acquisition_only", "uids": args.uid,
                                  "formats": formats, "remote_calls": 0}))
            else:
                from .asset_collection import collect_with_agent
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                directory = reserve_run_dir(args.out or ROOT / "runs" / ("asset-collection-" + stamp))
                packet = asyncio.run(collect_with_agent(args.uid, formats, directory, args.key_file, args.sketchfab_token_file))
                print(f"{packet['status']}: {directory / 'packet.json'}")
        except Exception as exc:
            parser.exit(1, f"Asset operation stopped ({type(exc).__name__}); error body withheld.\n")
        return
    config = load_config()
    if args.command == "doctor":
        versions = {}
        for package in ("openai-agents", "openai", "pydantic", "langflow"):
            try:
                versions[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                versions[package] = "not installed in this Python"
        print(json.dumps({"packages": versions, "organization_id": config["organization_id"],
                          "project_id": config["project_id"], "remote_calls": 0}, indent=2))
        return
    try:
        packet = prepare(args.request_file, args.specialist, config, args.use_platform_settings, args.reasoning)
        # Refuse overwriting an old run. No credentials are read in the offline path.
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        directory = reserve_run_dir(args.out or ROOT / "runs" / stamp)
        save_packet(packet, directory)
        if args.live:
            asyncio.run(run_live(packet, config, directory, args.key_file))
        print(f"{packet['status']}: {directory / 'packet.json'}")
    except Exception as exc:
        parser.exit(1, f"Stopped ({type(exc).__name__}); no raw error body logged. See a saved packet if created.\n")


if __name__ == "__main__":
    main()
