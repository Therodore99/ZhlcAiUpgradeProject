from pathlib import Path
from typing import Any, Optional


def find_previous_snapshot(
    version_dir: Path,
    current_snapshot_time: str,
) -> Optional[Path]:
    if not version_dir.exists():
        return None

    candidates = [
        path
        for path in version_dir.iterdir()
        if path.is_dir()
        and path.name != current_snapshot_time
        and (path / "manifest.json").is_file()
    ]
    candidates.sort(key=lambda path: path.name, reverse=True)
    return candidates[0] if candidates else None


def generate_diff(
    current_manifest: dict[str, Any],
    previous_manifest: Optional[dict[str, Any]],
) -> dict[str, Any]:
    current_files = current_manifest.get("files", [])
    new_map = {file["relative_path"]: file for file in current_files}

    if previous_manifest is None:
        added = [_simple_file_entry(file) for file in current_files]
        return {
            "env": current_manifest["env"],
            "version_date": current_manifest["version_date"],
            "mode": "full",
            "base_snapshot": None,
            "current_snapshot": current_manifest["snapshot_time"],
            "added": added,
            "modified": [],
            "deleted": [],
            "summary": {
                "added_count": len(added),
                "modified_count": 0,
                "deleted_count": 0,
                "unchanged_count": 0,
            },
        }

    old_map = {
        file["relative_path"]: file
        for file in previous_manifest.get("files", [])
    }

    added = [
        _simple_file_entry(new_map[path])
        for path in sorted(set(new_map) - set(old_map))
    ]
    deleted = [
        _simple_file_entry(old_map[path])
        for path in sorted(set(old_map) - set(new_map))
    ]
    modified = []
    unchanged_count = 0

    for path in sorted(set(new_map) & set(old_map)):
        changed_fields = [
            field
            for field in ("size", "mtime_epoch", "sha256")
            if new_map[path].get(field) != old_map[path].get(field)
        ]
        if changed_fields:
            modified.append(
                {
                    "relative_path": path,
                    "category": new_map[path]["category"],
                    "changed_fields": changed_fields,
                }
            )
        else:
            unchanged_count += 1

    return {
        "env": current_manifest["env"],
        "version_date": current_manifest["version_date"],
        "mode": "incremental",
        "base_snapshot": previous_manifest.get("snapshot_time"),
        "current_snapshot": current_manifest["snapshot_time"],
        "added": added,
        "modified": modified,
        "deleted": deleted,
        "summary": {
            "added_count": len(added),
            "modified_count": len(modified),
            "deleted_count": len(deleted),
            "unchanged_count": unchanged_count,
        },
    }


def _simple_file_entry(file: dict[str, Any]) -> dict[str, Any]:
    return {
        "relative_path": file["relative_path"],
        "category": file["category"],
    }
