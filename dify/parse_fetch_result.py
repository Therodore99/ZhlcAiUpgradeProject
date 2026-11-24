"""Dify Python 代码节点；输入 body 绑定 HTTP 取包节点的 body。"""
import json


TEXT_FIELDS = (
    "status", "step", "system", "env", "version_date", "message", "error",
)
DATA_FIELDS = (
    "mode", "snapshot_time", "snapshot_dir", "version_dir", "package_dir",
    "archive_file", "manifest_file", "diff_file", "upgrade_plan_file",
    "local_dir", "remote_dir", "actual_remote_dir", "expected_remote_dir",
    "parent_dir", "encoding",
)
COUNTS = (
    "file_count", "added_count", "modified_count", "deleted_count", "unchanged_count",
    "so_changed", "sql_changed", "ufx_changed", "microservice_changed",
    "schedule_task_changed", "workflow_changed", "project_config_changed", "other_changed",
    "config_changed", "bus_component_changed", "plugin_changed", "route_config_changed",
    "upgrade_notes_count",
)


def main(body):
    try:
        obj = json.loads(body) if isinstance(body, str) else body
    except ValueError:
        obj = None
    if not isinstance(obj, dict):
        obj = {"status": "failed", "message": "HTTP body 不是有效的 JSON 对象"}
    data = obj.get("data") if isinstance(obj.get("data"), dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    out = {key: str(obj.get(key) or "") for key in TEXT_FIELDS}
    out["status"] = out["status"] or "failed"
    out.update({key: str(data.get(key) or "") for key in DATA_FIELDS})
    for key in COUNTS:
        try:
            out[key] = int(summary.get(key, data.get(key, 0) if key == "file_count" else 0))
        except (ValueError, TypeError):
            out[key] = 0
    out["upgrade_notes_present"] = summary.get("upgrade_notes_present") is True
    for key, items in (("upgrade_notes_files_text", summary.get("upgrade_notes_files")),
                       ("warnings_text", obj.get("warnings"))):
        out[key] = "\n".join(str(item) for item in items) if isinstance(items, list) else ""
    return out
