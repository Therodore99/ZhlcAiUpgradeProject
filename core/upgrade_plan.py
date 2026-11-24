from typing import Any, Optional

# 此表只定义计划字段，不包含任何执行动作。
TASK_FLAGS = {
    "legacy_account": {
        "so": "need_run", "sql": "need_run", "ufx": "need_run",
        "microservice": "need_notify", "schedule_task": "need_notify",
        "workflow": "need_notify", "project_config": "need_notify", "other": "need_notify",
    },
    "bus": {"bus_component": "need_notify"},
    "xinchuang_account": {
        "schedule_task": "need_notify", "config": "need_run", "sql": "need_run",
        "microservice": "need_notify", "plugin": "need_notify", "route_config": "need_notify",
    },
}


def generate_upgrade_plan(diff: dict[str, Any], manifest: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    system = diff.get("system", "legacy_account")
    flags = TASK_FLAGS[system]
    grouped: dict[str, list[str]] = {category: [] for category in flags}
    grouped.setdefault("other", [])
    for entry in diff["added"] + diff["modified"]:
        if entry["category"] in grouped:
            grouped[entry["category"]].append(entry["relative_path"])

    tasks = {
        category: {flag: bool(grouped[category]) and category != "other", "files": grouped[category]}
        for category, flag in flags.items()
    }
    if "sql" in tasks:
        tasks["sql"]["need_manual_confirm"] = True
    summary: dict[str, Any] = {f"{category}_changed": len(files) for category, files in grouped.items()}
    if system == "xinchuang_account":
        if manifest is None:
            raise ValueError("信创升级说明提醒需要当前 manifest。")
        notes = [f["relative_path"] for f in manifest["files"] if f["category"] == "documentation"]
        tasks["documentation"] = {"need_notify": bool(notes), "files": notes}
        summary.update(upgrade_notes_present=bool(notes), upgrade_notes_count=len(notes), upgrade_notes_files=notes)

    return {
        "system": system,
        "env": diff["env"],
        "version_date": diff["version_date"],
        "snapshot_time": diff["current_snapshot"],
        "mode": diff["mode"],
        "tasks": tasks,
        "summary": summary,
    }
