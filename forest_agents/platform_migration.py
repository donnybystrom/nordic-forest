"""Explicit, resumable copy-verify-remove operation for the authorized project split.

This module has no command-line entry point. Review the manifest before invoking
its operations. Secret keys are passed through clients, never serialized.
"""
import hashlib
import json

CONFIG_FIELDS = ("name", "model", "instructions", "reasoning", "text", "service_tier", "tools", "multi_agent", "metadata")


def definition(agent):
    data = agent.model_dump(mode="json") if hasattr(agent, "model_dump") else agent
    return {k: data[k] for k in CONFIG_FIELDS}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def exact_clone(source_client, target_client, agent_id, manifest, save):
    source = definition(source_client.beta.agents.retrieve(agent_id))
    record = manifest["copies"].setdefault(agent_id, {"source_sha256": digest(source)})
    if record["source_sha256"] != digest(source):
        raise ValueError("Source definition changed since migration began")
    if "target_id" not in record:
        payload = json.loads(json.dumps(source))
        # Retrieval resolves a disabled limit to null; creation accepts omission,
        # but rejects explicit null. Preserve the resolved definition on readback.
        if payload["multi_agent"].get("max_concurrent_subagents") is None:
            payload["multi_agent"].pop("max_concurrent_subagents", None)
        # Stable idempotency key also handles an unknown POST outcome on retry.
        token = digest({"source_id": agent_id, "target_project": manifest["target_project"], "definition": payload})
        created = target_client.beta.agents.create(**payload, extra_headers={"Idempotency-Key": "forest-split-" + token})
        record["target_id"] = created.id
        save()
    restored = definition(target_client.beta.agents.retrieve(record["target_id"]))
    if restored != source:
        raise ValueError("Target definition differs from source")
    record["target_verified_sha256"] = digest(restored)
    record["name"] = source["name"]
    save()
    return record


def remove_verified_sources(source_client, target_client, manifest, save):
    # Recheck EVERY copy before the first removal, not just one copy at a time.
    if not manifest["copies"] or len(manifest["copies"]) != manifest["expected_count"]:
        raise ValueError("Incomplete migration manifest")
    for old_id, record in manifest["copies"].items():
        target = definition(target_client.beta.agents.retrieve(record["target_id"]))
        if digest(target) != record["source_sha256"]:
            raise ValueError("Target changed; refusing source removal")
        if not record.get("source_removed"):
            source = definition(source_client.beta.agents.retrieve(old_id))
            if digest(source) != record["source_sha256"]:
                raise ValueError("Source changed; refusing removal")
    for old_id, record in manifest["copies"].items():
        if record.get("source_removed"):
            continue
        result = source_client.beta.agents.delete(old_id)
        if not result.deleted:
            raise ValueError("Source removal not confirmed")
        record["source_removed"] = True
        save()
