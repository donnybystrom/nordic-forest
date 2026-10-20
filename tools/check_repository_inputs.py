"""Reject secret-looking blobs, reference payloads and oversized regular Git inputs."""
import re
import subprocess


def inspect_index():
    entries = subprocess.check_output(['git', 'ls-files', '--stage', '-z']).split(b'\0')
    rejected, count, total, biggest = [], 0, 0, 0
    for entry in entries:
        if not entry:
            continue
        meta, raw_path = entry.split(b'\t', 1)
        mode, oid, stage = meta.split()
        path = raw_path.decode()
        if stage != b'0':
            rejected.append((path, 'unresolved conflict'));continue
        blob = subprocess.check_output(['git', 'cat-file', 'blob', oid.decode()])
        size = len(blob);count += 1;total += size;biggest = max(biggest, size)
        lower = path.lower()
        basename = lower.rsplit('/', 1)[-1]
        if (any(v in lower for v in ['secret_key', 'api_token']) or lower.startswith('runs/')
                or (basename.startswith('.env') and basename != '.env.example') or lower.endswith(('.pem', '.key'))):
            rejected.append((path, 'local/secret path'))
        if lower.startswith('data/references/'):
            rest = path[len('data/references/'):]
            if not (rest.endswith('.json') and ('/' not in rest or (rest.startswith('analysis/') and rest.count('/') == 1))):
                rejected.append((path, 'third-party reference payload'))
        if size > 10 * 1024 * 1024:
            rejected.append((path, 'regular Git blob exceeds project 10 MiB limit'))
        if size <= 10 * 1024 * 1024 and re.search(rb'(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,})', blob):
            rejected.append((path, 'credential-like value'))
    return {'indexed_files': count, 'indexed_bytes': total, 'largest_blob_bytes': biggest, 'rejected': rejected}


if __name__ == '__main__':
    import json
    result=inspect_index();print(json.dumps(result,indent=2));raise SystemExit(bool(result['rejected']))
