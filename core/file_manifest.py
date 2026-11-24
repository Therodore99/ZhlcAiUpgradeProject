import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any


def generate_manifest(
    package_dir: Path,
    env: str,
    version_date: str,
    snapshot_time: str,
    category_profile: str = "legacy_account",
) -> dict[str, Any]:
    files = []
    for path in sorted(package_dir.rglob("*")):
        if not path.is_file():
            continue

        relative_path = _to_relative_path(path, package_dir)
        stat_result = path.stat()
        files.append(
            {
                "relative_path": relative_path,
                "category": categorize_file(relative_path, category_profile),
                "file_name": path.name,
                "size": stat_result.st_size,
                "mtime": datetime.fromtimestamp(stat_result.st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "mtime_epoch": int(stat_result.st_mtime),
                "sha256": _calculate_sha256(path),
            }
        )

    return {
        "system": category_profile,
        "env": env,
        "version_date": version_date,
        "snapshot_time": snapshot_time,
        "package_dir": str(package_dir.resolve()),
        "file_count": len(files),
        "files": files,
    }


XINCHUANG_DIRS = {
    "AcctDsrw": "schedule_task", "Config": "config", "Sql": "sql",
    "升级说明": "documentation", "微服务": "microservice",
    "特殊插件": "plugin", "路由配置文件": "route_config",
}


def categorize_file(relative_path: str, category_profile: str = "legacy_account") -> str:
    normalized_path = relative_path.replace("\\", "/")
    parts = normalized_path.split("/")
    lower_parts = [part.lower() for part in parts]
    suffix = Path(normalized_path).suffix.lower()

    if category_profile == "bus":
        return "bus_component" if suffix == ".zip" else "other"
    if category_profile == "xinchuang_account":
        return XINCHUANG_DIRS.get(parts[0], "other") if len(parts) > 1 else "other"
    if category_profile != "legacy_account":
        raise ValueError(f"未知分类策略: {category_profile}")

    if "appcom" in lower_parts and suffix == ".so":
        return "so"

    if "sql" in lower_parts and suffix == ".sql":
        return "sql"

    if "其他程序" in parts and "ufx" in lower_parts and suffix == ".xml":
        return "ufx"

    if "微服务" in parts and suffix == ".zip":
        return "microservice"

    if "账户定时任务" in parts and suffix == ".zip":
        if "定时任务" in parts:
            return "schedule_task"
        if "工作流" in parts:
            return "workflow"
        if "项目配置" in parts:
            return "project_config"

    return "other"


def _to_relative_path(path: Path, package_dir: Path) -> str:
    return path.relative_to(package_dir).as_posix()


def _calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
