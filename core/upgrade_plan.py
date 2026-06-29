from typing import Any

CATEGORIES = [
    "so",
    "sql",
    "ufx",
    "schedule_task",
    "workflow",
    "project_config",
    "other",
]


def generate_upgrade_plan(diff: dict[str, Any]) -> dict[str, Any]:
    changed_files = diff.get("added", []) + diff.get("modified", [])
    grouped_files = {category: [] for category in CATEGORIES}
    for file in changed_files:
        category = file.get("category", "other")
        if category not in grouped_files:
            category = "other"
        grouped_files[category].append(file["relative_path"])

    tasks = {
        "so": {
            "need_run": bool(grouped_files["so"]),
            "files": grouped_files["so"],
        },
        "sql": {
            "need_run": bool(grouped_files["sql"]),
            "need_manual_confirm": True,
            "files": grouped_files["sql"],
        },
        "ufx": {
            "need_run": bool(grouped_files["ufx"]),
            "files": grouped_files["ufx"],
        },
        "schedule_task": {
            "need_notify": bool(grouped_files["schedule_task"]),
            "files": grouped_files["schedule_task"],
        },
        "workflow": {
            "need_notify": bool(grouped_files["workflow"]),
            "files": grouped_files["workflow"],
        },
        "project_config": {
            "need_notify": bool(grouped_files["project_config"]),
            "files": grouped_files["project_config"],
        },
        "other": {
            "need_notify": False,
            "files": grouped_files["other"],
        },
    }

    return {
        "env": diff["env"],
        "version_date": diff["version_date"],
        "snapshot_time": diff["current_snapshot"],
        "mode": diff["mode"],
        "tasks": tasks,
        "summary": {
            f"{category}_changed": len(grouped_files[category])
            for category in CATEGORIES
        },
    }
