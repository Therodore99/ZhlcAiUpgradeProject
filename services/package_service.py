import json
import shlex
import shutil
import tarfile
import time
from datetime import datetime
from os.path import commonpath
from pathlib import Path
from typing import Any, Optional

from core.config_manager import ConfigError, ConfigManager
from core.file_diff import find_previous_snapshot, generate_diff
from core.file_manifest import generate_manifest
from core.logger import get_logger
from core.response import build_response
from core.ssh_manager import SSHManager
from core.upgrade_plan import generate_upgrade_plan
from schemas.package_schema import FetchPackageRequest

logger = get_logger()
PARENT_NOT_FOUND_MARKER = "__ACCOUNT_UPGRADE_PARENT_NOT_FOUND__"


def fetch_package(request: FetchPackageRequest) -> dict[str, Any]:
    start_time = time.time()
    warnings: list[str] = []
    remote_archive: Optional[str] = None
    ssh_manager: Optional[SSHManager] = None
    response_context: dict[str, Any] = {}

    logger.info(
        "fetch_package start env=%s year=%s version_date=%s force=%s debug=%s",
        request.env,
        request.year,
        request.version_date,
        request.force,
        request.debug,
    )

    try:
        package_config = ConfigManager().get_package_config(request.env)
        encoding = package_config["encoding"]
        parent_dir = _build_parent_dir(package_config, request.year)
        expected_remote_dir = _build_remote_dir(package_config, request.year, request.version_date)
        version_dir = _build_version_dir(package_config, request.version_date)
        snapshot_time = _generate_snapshot_time(version_dir)
        snapshot_dir = version_dir / snapshot_time
        package_dir = snapshot_dir / "package"
        archive_file = snapshot_dir / f"account_upgrade_{request.version_date}.tar.gz"
        manifest_file = snapshot_dir / "manifest.json"
        diff_file = snapshot_dir / "diff_from_previous.json"
        upgrade_plan_file = snapshot_dir / "upgrade_plan.json"
        latest_file = version_dir / "latest.txt"
        remote_archive = _build_remote_archive(
            package_config,
            request.env,
            request.version_date,
        )
        response_context = {
            "encoding": encoding,
            "parent_dir": parent_dir,
            "candidates": [],
            "expected_remote_dir": expected_remote_dir,
            "actual_remote_dir": None,
            "version_dir": str(version_dir),
            "snapshot_dir": str(snapshot_dir),
            "snapshot_time": snapshot_time,
            "package_dir": str(package_dir),
            "manifest_file": str(manifest_file),
            "diff_file": str(diff_file),
            "upgrade_plan_file": str(upgrade_plan_file),
        }

        logger.info(
            "paths encoding=%s parent_dir=%s expected_remote_dir=%s "
            "version_dir=%s snapshot_dir=%s package_dir=%s",
            encoding,
            parent_dir,
            expected_remote_dir,
            version_dir,
            snapshot_dir,
            package_dir,
        )

        if not request.force:
            latest_response_data = _build_latest_snapshot_data(
                latest_file,
                response_context,
                expected_remote_dir,
            )
            if latest_response_data:
                elapsed = time.time() - start_time
                logger.info(
                    "fetch_package reused latest snapshot version_dir=%s snapshot_dir=%s "
                    "mode=%s summary=%s elapsed=%.2fs",
                    latest_response_data.get("version_dir"),
                    latest_response_data.get("snapshot_dir"),
                    latest_response_data.get("mode"),
                    latest_response_data.get("summary"),
                    elapsed,
                )
                return build_response(
                    status="success",
                    step="fetch_package",
                    env=request.env,
                    version_date=request.version_date,
                    message="已有可用 snapshot，本次未重新下载",
                    data=latest_response_data,
                    warnings=warnings,
                )

        version_dir.mkdir(parents=True, exist_ok=True)
        snapshot_dir.mkdir(parents=True, exist_ok=False)
        package_dir.mkdir(parents=True, exist_ok=True)

        try:
            previous_snapshot = find_previous_snapshot(version_dir, snapshot_time)
        except OSError as exc:
            logger.exception("find previous snapshot failed")
            return _failed_response(request, "find_previous_snapshot", "取包失败", exc, warnings, response_context)

        if previous_snapshot is not None:
            logger.info("previous snapshot found snapshot_dir=%s", previous_snapshot)
        else:
            logger.info("previous snapshot not found version_dir=%s", version_dir)

        try:
            previous_manifest = _load_json(previous_snapshot / "manifest.json") if previous_snapshot else None
        except Exception as exc:
            logger.exception("load previous manifest failed")
            return _failed_response(request, "load_previous_manifest", "取包失败", exc, warnings, response_context)

        try:
            ssh_manager = SSHManager(
                host=package_config["host"],
                port=int(package_config["port"]),
                username=package_config["username"],
                password=package_config["password"],
                connect_timeout=int(package_config["connect_timeout"]),
                encoding=encoding,
            )
            ssh_manager.connect()
            logger.info("ssh_connect success host=%s port=%s", package_config["host"], package_config["port"])
        except Exception as exc:
            logger.exception("ssh_connect failed")
            return _failed_response(request, "ssh_connect", "取包失败", exc, warnings, response_context)

        command_timeout = int(package_config["command_timeout"])
        try:
            parent_exists, candidates = _list_remote_package_candidates(
                ssh_manager,
                parent_dir,
                command_timeout,
            )
        except Exception as exc:
            logger.exception("remote_list failed")
            return _failed_response(request, "remote_list", "取包失败", exc, warnings, response_context)

        response_context["candidates"] = candidates
        actual_dir_name = _select_package_dir(candidates, request.version_date)
        if parent_exists and actual_dir_name is not None:
            actual_remote_dir = f"{parent_dir.rstrip('/')}/{actual_dir_name}"
            response_context["actual_remote_dir"] = actual_remote_dir
        else:
            actual_remote_dir = None

        logger.info(
            "remote candidates encoding=%s parent_dir=%s expected_remote_dir=%s "
            "actual_remote_dir=%s candidates=%s",
            encoding,
            parent_dir,
            expected_remote_dir,
            actual_remote_dir,
            candidates,
        )

        if actual_remote_dir is None:
            return build_response(
                status="not_found",
                step="fetch_package",
                env=request.env,
                version_date=request.version_date,
                message="未发现当前版本升级包目录，等待下次触发",
                data={
                    **response_context,
                    "remote_dir": expected_remote_dir,
                },
                warnings=warnings,
            )

        tar_result = ssh_manager.execute_command(
            f"cd {shlex.quote(actual_remote_dir)} && tar -czf {shlex.quote(remote_archive)} .",
            timeout=command_timeout,
        )
        if tar_result.exit_status != 0:
            logger.error("remote_tar failed stdout=%s stderr=%s", tar_result.stdout, tar_result.stderr)
            return _failed_response(
                request,
                "remote_tar",
                "取包失败",
                RuntimeError(tar_result.stderr or tar_result.stdout or "远程压缩失败"),
                warnings,
                response_context,
            )
        logger.info(
            "remote_tar success encoding=%s actual_remote_dir=%s remote_archive=%s",
            encoding,
            actual_remote_dir,
            remote_archive,
        )

        try:
            ssh_manager.download_file(remote_archive, archive_file)
            logger.info("scp_download success archive_file=%s", archive_file)
        except Exception as exc:
            logger.exception("scp_download failed")
            return _failed_response(request, "scp_download", "取包失败", exc, warnings, response_context)
        finally:
            cleanup_warning = _cleanup_remote_archive(ssh_manager, remote_archive, command_timeout)
            if cleanup_warning:
                warnings.append(cleanup_warning)

        try:
            extracted_file_count = _extract_archive(
                archive_file,
                package_dir,
                encoding,
                request.force,
            )
            logger.info(
                "extract_archive success archive_file=%s extract_dir=%s "
                "encoding=%s extracted_file_count=%s",
                archive_file,
                package_dir,
                encoding,
                extracted_file_count,
            )
        except Exception as exc:
            logger.exception("extract_archive failed")
            return _failed_response(request, "extract_archive", "取包失败", exc, warnings, response_context)

        try:
            manifest = generate_manifest(
                package_dir=package_dir,
                env=request.env,
                version_date=request.version_date,
                snapshot_time=snapshot_time,
            )
            _write_json(manifest_file, manifest)
            diff = generate_diff(manifest, previous_manifest)
            _write_json(diff_file, diff)
            upgrade_plan = generate_upgrade_plan(diff)
            _write_json(upgrade_plan_file, upgrade_plan)
            _write_text(latest_file, str(snapshot_dir.resolve()))
        except Exception as exc:
            logger.exception("generate snapshot metadata failed")
            return _failed_response(request, "generate_snapshot_metadata", "取包失败", exc, warnings, response_context)

        file_count = manifest["file_count"]
        warnings.extend(_check_required_dirs(package_dir))
        summary = _build_response_summary(manifest, diff, upgrade_plan)
        elapsed = time.time() - start_time
        logger.info(
            "fetch_package success encoding=%s parent_dir=%s expected_remote_dir=%s "
            "actual_remote_dir=%s candidates=%s version_dir=%s snapshot_dir=%s "
            "package_dir=%s manifest_file=%s diff_file=%s upgrade_plan_file=%s "
            "mode=%s added_count=%s modified_count=%s deleted_count=%s "
            "so_changed=%s sql_changed=%s ufx_changed=%s microservice_changed=%s "
            "schedule_task_changed=%s workflow_changed=%s project_config_changed=%s "
            "file_count=%s warnings=%s elapsed=%.2fs",
            encoding,
            parent_dir,
            expected_remote_dir,
            actual_remote_dir,
            candidates,
            version_dir,
            snapshot_dir,
            package_dir,
            manifest_file,
            diff_file,
            upgrade_plan_file,
            diff["mode"],
            summary["added_count"],
            summary["modified_count"],
            summary["deleted_count"],
            summary["so_changed"],
            summary["sql_changed"],
            summary["ufx_changed"],
            summary["microservice_changed"],
            summary["schedule_task_changed"],
            summary["workflow_changed"],
            summary["project_config_changed"],
            file_count,
            warnings,
            elapsed,
        )

        return build_response(
            status="success",
            step="fetch_package",
            env=request.env,
            version_date=request.version_date,
            message="取包完成",
            data={
                **response_context,
                "remote_dir": actual_remote_dir,
                "local_dir": str(package_dir),
                "archive_file": str(archive_file),
                "file_count": file_count,
                "mode": diff["mode"],
                "summary": summary,
            },
            warnings=warnings,
        )

    except ConfigError as exc:
        logger.error("config error: %s", exc)
        return _failed_response(request, "config", "取包失败", exc, warnings)
    except Exception as exc:
        logger.exception("fetch_package unexpected failed")
        return _failed_response(request, "fetch_package", "取包失败", exc, warnings, response_context)
    finally:
        if ssh_manager is not None:
            ssh_manager.close()
        elapsed = time.time() - start_time
        logger.info("fetch_package end elapsed=%.2fs", elapsed)


def _build_remote_dir(package_config: dict[str, Any], year: str, version_date: str) -> str:
    package_name = package_config["package_name_template"].format(version_date=version_date)
    return f"{_build_parent_dir(package_config, year)}/{package_name}"


def _build_parent_dir(package_config: dict[str, Any], year: str) -> str:
    return f"{package_config['remote_root'].rstrip('/')}/{year}"


def _build_version_dir(package_config: dict[str, Any], version_date: str) -> Path:
    return Path(package_config["local_root"]) / version_date


def _build_remote_archive(package_config: dict[str, Any], env: str, version_date: str) -> str:
    return (
        f"{package_config['remote_temp_dir'].rstrip('/')}/"
        f"account_upgrade_{env}_{version_date}.tar.gz"
    )


def _generate_snapshot_time(version_dir: Path) -> str:
    while True:
        snapshot_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not (version_dir / snapshot_time).exists():
            return snapshot_time
        time.sleep(1)


def _build_latest_snapshot_data(
    latest_file: Path,
    response_context: dict[str, Any],
    expected_remote_dir: str,
) -> Optional[dict[str, Any]]:
    if not latest_file.is_file():
        return None

    try:
        snapshot_dir = Path(latest_file.read_text(encoding="utf-8").strip())
        manifest_file = snapshot_dir / "manifest.json"
        diff_file = snapshot_dir / "diff_from_previous.json"
        upgrade_plan_file = snapshot_dir / "upgrade_plan.json"
        if not (
            snapshot_dir.is_dir()
            and manifest_file.is_file()
            and diff_file.is_file()
            and upgrade_plan_file.is_file()
        ):
            return None

        manifest = _load_json(manifest_file)
        diff = _load_json(diff_file)
        upgrade_plan = _load_json(upgrade_plan_file)
    except Exception as exc:
        logger.warning("latest snapshot unavailable latest_file=%s error=%s", latest_file, exc)
        return None

    version_date = manifest.get("version_date", "")
    package_dir = Path(manifest.get("package_dir", snapshot_dir / "package"))
    archive_file = snapshot_dir / f"account_upgrade_{version_date}.tar.gz"
    summary = _build_response_summary(manifest, diff, upgrade_plan)

    return {
        **response_context,
        "remote_dir": expected_remote_dir,
        "local_dir": str(package_dir),
        "version_dir": str(latest_file.parent),
        "snapshot_dir": str(snapshot_dir),
        "snapshot_time": snapshot_dir.name,
        "package_dir": str(package_dir),
        "archive_file": str(archive_file),
        "manifest_file": str(manifest_file),
        "diff_file": str(diff_file),
        "upgrade_plan_file": str(upgrade_plan_file),
        "file_count": manifest.get("file_count", 0),
        "mode": diff.get("mode"),
        "summary": summary,
    }


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_response_summary(
    manifest: dict[str, Any],
    diff: dict[str, Any],
    upgrade_plan: dict[str, Any],
) -> dict[str, int]:
    diff_summary = diff.get("summary", {})
    plan_summary = upgrade_plan.get("summary", {})
    return {
        "file_count": int(manifest.get("file_count", 0)),
        "added_count": int(diff_summary.get("added_count", 0)),
        "modified_count": int(diff_summary.get("modified_count", 0)),
        "deleted_count": int(diff_summary.get("deleted_count", 0)),
        "unchanged_count": int(diff_summary.get("unchanged_count", 0)),
        "so_changed": int(plan_summary.get("so_changed", 0)),
        "sql_changed": int(plan_summary.get("sql_changed", 0)),
        "ufx_changed": int(plan_summary.get("ufx_changed", 0)),
        "microservice_changed": int(plan_summary.get("microservice_changed", 0)),
        "schedule_task_changed": int(plan_summary.get("schedule_task_changed", 0)),
        "workflow_changed": int(plan_summary.get("workflow_changed", 0)),
        "project_config_changed": int(plan_summary.get("project_config_changed", 0)),
        "other_changed": int(plan_summary.get("other_changed", 0)),
    }


def _list_remote_package_candidates(
    ssh_manager: SSHManager,
    parent_dir: str,
    timeout: int,
) -> tuple[bool, list[str]]:
    command = (
        f"if test -d {shlex.quote(parent_dir)}; then "
        f"cd {shlex.quote(parent_dir)} && find . -maxdepth 1 -mindepth 1 -type d -print; "
        f"else echo {PARENT_NOT_FOUND_MARKER}; fi"
    )
    result = ssh_manager.execute_command(command, timeout=timeout)
    if result.exit_status != 0:
        raise RuntimeError(result.stderr or result.stdout or "远程目录候选列表获取失败")

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if PARENT_NOT_FOUND_MARKER in lines:
        return False, []

    return True, [_normalize_find_dir(line) for line in lines]


def _normalize_find_dir(path: str) -> str:
    if path == ".":
        return ""
    if path.startswith("./"):
        return path[2:]
    return path.rstrip("/")


def _select_package_dir(candidates: list[str], version_date: str) -> Optional[str]:
    version_candidates = [name for name in candidates if version_date in name]
    preferred_candidates = [name for name in version_candidates if "小远期" in name]
    if preferred_candidates:
        return preferred_candidates[0]
    if version_candidates:
        return version_candidates[0]
    return None


def _cleanup_remote_archive(
    ssh_manager: Optional[SSHManager],
    remote_archive: Optional[str],
    timeout: int,
) -> Optional[str]:
    if ssh_manager is None or remote_archive is None:
        return None
    try:
        result = ssh_manager.execute_command(f"rm -f {shlex.quote(remote_archive)}", timeout=timeout)
        if result.exit_status != 0:
            logger.warning("cleanup remote archive failed stderr=%s", result.stderr)
            return f"远程临时压缩包清理失败: {result.stderr or result.stdout}"
    except Exception as exc:
        logger.warning("cleanup remote archive exception: %s", exc)
        return f"远程临时压缩包清理失败: {exc}"
    return None


def _extract_archive(
    archive_file: Path,
    local_dir: Path,
    encoding: str,
    force: bool,
) -> int:
    if force:
        _clean_extract_dir(local_dir, archive_file)

    try:
        with tarfile.open(
            archive_file,
            mode="r:gz",
            encoding=encoding,
            errors="replace",
        ) as tar:
            members = tar.getmembers()
            _safe_extract(tar, local_dir, members)
            return _count_member_files(members)
    except TypeError:
        # 兼容不支持 tarfile.open encoding/errors 参数的旧 Python。
        with tarfile.open(archive_file, mode="r:gz") as tar:
            members = tar.getmembers()
            for member in members:
                member.name = _repair_tar_name(member.name, encoding)
                if member.linkname:
                    member.linkname = _repair_tar_name(member.linkname, encoding)
            _safe_extract(tar, local_dir, members)
            return _count_member_files(members)


def _clean_extract_dir(local_dir: Path, archive_file: Path) -> None:
    if not local_dir.exists():
        return

    archive_file = archive_file.resolve()
    for path in local_dir.iterdir():
        if path.resolve() == archive_file:
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def _repair_tar_name(name: str, encoding: str) -> str:
    for source_encoding, errors in (("utf-8", "surrogateescape"), ("latin-1", "strict")):
        try:
            return name.encode(source_encoding, errors=errors).decode(encoding, errors="replace")
        except UnicodeError:
            continue
    return name


def _safe_extract(
    tar: tarfile.TarFile,
    target_dir: Path,
    members: Optional[list[tarfile.TarInfo]] = None,
) -> None:
    target_dir = target_dir.resolve()
    members = members if members is not None else tar.getmembers()
    for member in members:
        member_path = (target_dir / member.name).resolve()
        # 保守处理归档路径，避免异常包内容解压到目标目录之外。
        if commonpath([str(target_dir), str(member_path)]) != str(target_dir):
            raise RuntimeError(f"压缩包包含非法路径: {member.name}")
    tar.extractall(target_dir, members=members)


def _count_member_files(members: list[tarfile.TarInfo]) -> int:
    return sum(1 for member in members if member.isfile())


def _count_files(local_dir: Path) -> int:
    if not local_dir.exists():
        return 0
    return sum(1 for path in local_dir.rglob("*") if path.is_file())


def _check_required_dirs(local_dir: Path) -> list[str]:
    warnings: list[str] = []
    for dirname in ("appcom", "sql", "其他程序"):
        if not (local_dir / dirname).is_dir():
            warnings.append(f"本地升级包目录缺少关键目录: {dirname}")
    return warnings


def _failed_response(
    request: FetchPackageRequest,
    step: str,
    message: str,
    exc: Exception,
    warnings: Optional[list[str]] = None,
    data: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return build_response(
        status="failed",
        step=step,
        env=request.env,
        version_date=request.version_date,
        message=message,
        data=data,
        warnings=warnings or [],
        error=str(exc),
    )
