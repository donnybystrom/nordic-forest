# Repository inputs and large assets

Keep code, prompts, configurations, flow JSON, manifests, source/license metadata, small reference screenshots and analysis summaries in ordinary Git. Keep acquired third-party payloads, unpacked game/mod resources, generated jobs, service credentials and build/export output local.

The initial `.gitignore` denies content below `data/references/` by default and admits only top-level JSON and JSON summaries directly below `analysis/`. A new reference folder is therefore ignored without needing to enumerate every mod name. The source screenshot folder under `assets/references/screenshots/` remains versioned separately.

On 18 October 2026, 2,235 previously staged Skyrim reference files (5,794,975,426 bytes on disk) were removed from the index. Every file remained on disk. No reference payload was present in the initial committed tree. The remaining 76 indexed files occupied about 2.7 MB of blob data; the largest was 899,736 bytes. These are an audit checkpoint, not a permanent count after new source files are added.

`.gitignore` does not untrack staged or committed files. The cleanup used an exact NUL-delimited list and `git restore --staged`; it did not delete working files or rewrite history. Local Git objects from previous staging may still occupy disk until normal Git maintenance; index cleanup is not a claim of reclaimed APFS space.

`tools/check_repository_inputs.py` checks indexed blobs and rejects reference payload paths, secret-like inputs and ordinary Git blobs over the project's 10 MiB limit. It also runs in the supplied CI. That project limit is deliberately smaller than GitHub's 100 MiB hard limit. [GitHub file limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github).

Use **Git LFS** selectively when original, authored binary assets need version history—for example the project's own Blender source. LFS stores a pointer in Git and the large contents separately; storage and transfer limits depend on the hosting plan. No broad LFS tracking or history migration has been applied here. Do not upload all downloaded references merely to avoid a Git file-size error. [Git LFS](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage).
