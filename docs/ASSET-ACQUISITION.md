# Sketchfab asset acquisition

The backend can retrieve assigned downloadable Sketchfab models, preserve author/source metadata and produce local hashed manifests. An SDK collection agent has the same narrow capability. Acquisition is separate from mesh analysis, conversion and production acceptance.

## Credentials and tool boundary

`SKETCHFAB_API_TOKEN.md` is read by the backend, or use the `SKETCHFAB_API_TOKEN` environment variable. The token authenticates only to `api.sketchfab.com`; provider-signed archive URLs are fetched separately without that token. Tokens and expiring signed URLs are absent from agent inputs, tool results and saved manifests.

The model-facing `fetch_sketchfab_reference` tool accepts only `model_uid` and `archive_format`. The host supplies an explicit UID/format allowlist and fixed cache location. The tool cannot accept an arbitrary URL, credential, output path, shell command or purchase instruction. No files are executed. The existing planning CLI remains planning-only; the collection workflow explicitly attaches the acquisition tool in a separate SDK agent.

Default acquisition limits: four archives per collector, 512 MiB per archive and 1 GiB total downloaded bytes. ZIP extraction validates paths/symlinks/duplicates and caps each archive at 2 GiB expanded and 12,000 entries. Network operations have a 30-second timeout; long streaming operations are byte-bounded. Partial downloads are retained on failure. Repeating an explicit fetch creates a new snapshot rather than overwriting an earlier source.

## Direct acquisition

No OpenAI model call is needed for deterministic collection:

```sh
python3 -m forest_agents assets-fetch --uid a5e4e64f9f1d4089bdcc6170a9333393 --format source --format glb
```

`source` preserves the author upload. `glb` and `gltf` are Sketchfab conversions and may differ in structure, attribute naming or dependencies. Keep them as distinct evidence. Each snapshot under `data/references/downloads/<uid>/` contains the archive/model, safely extracted files when it is a ZIP, and `manifest.json` with source/license metadata, sizes and SHA-256 hashes. The download directory and token files are ignored by Git.

## SDK collection agent

Prepare a request without network/model calls:

```sh
python3 -m forest_agents assets-agent --uid 0ab534c493e14f67bac01ee94f20e43f --format glb
```

Run the actual tool-enabled agent explicitly:

```sh
python3 -m forest_agents assets-agent --uid 0ab534c493e14f67bac01ee94f20e43f --format glb --live --key-file OPENAI_API_SECRET_KEY.md
```

This local runner uses gpt-6-luna with low reasoning, only the download tool, a bounded turn count, no automatic subagents, disabled tracing and a 600-second workflow wait. OpenAI calls are billed through the project key. Artifact manifests/tool events and returned token usage are stored in a fresh `runs/asset-collection-…/packet.json`. Final manifest claims are compared against actual backend results. A timed-out agent cannot certify an acquisition; inspect the persisted tool events and cache for completed files.

For another SDK workflow, instantiate `SketchfabCollector(allowed_uids=[...], allowed_formats=[...])` and attach `collector.agent_tools()`. Keep scope and budgets in the host. A platform agent name or a Langflow node does not automatically attach this local Python capability; a native Langflow adapter is still separate work.

## Source completeness and analysis handover

Pass actual model paths and manifests into the [reference asset pipeline](REFERENCE-ASSET-PIPELINE.md). The oak author's supplemental texture warning remains an explicit dependency until the archive and texture families are compared. A successful download does not prove all seasons, vertex masks or shader inputs survive a provider conversion.

For the supplied Skyrim references, the user is downloading Nature of the Wild Lands and Fabled Forests into `data/references/`. Their exact URLs and the supplied Nature file ID are registered in `catalog.json`. Record actual archive hashes and versions when complete files arrive; no Nexus API credential or automated Nexus download is configured.
