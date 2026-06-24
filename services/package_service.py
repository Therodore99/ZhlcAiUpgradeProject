import shlex
import tarfile
import time
from os.path import commonpath
from pathlib import Path
from typing import Any, Optional

from core.config_manager import ConfigError, ConfigManager
from core.logger import get_logger
from core.response import build_response
from core.ssh_manager import SSHManager
from schemas.package_schema import FetchPackageRequest

logger = get_logger()


def fetch_package(request: FetchPackageRequest) -> dict[str, Any]:
    start_time = time.time()
    warnings: list[str] = []
    remote_archive: Optional[str] = None
    ssh_manager: Optional[SSHManager] = None

    logger.info(
        "fetch_package start env=%s year=%s version_date=%s force=%s",
        request.env,
        request.year,
        request.version_date,
        request.force,
    )

    try:
        package_config = ConfigManager().get_package_config(request.env)
        remote_dir = _build_remote_dir(package_config, request.year, request.version_date)
        local_dir = _build_local_dir(package_config, request.version_date)
        archive_file = local_dir / f"account_upgrade_{request.version_date}.tar.gz"
        remote_archive = _build_remote_archive(
            package_config,
            request.env,
            request.version_date,
        )

        logger.info("paths remote_dir=%s local_dir=%s", remote_dir, local_dir)

        if not request.force and _has_local_files(local_dir):
            file_count = _count_files(local_dir)
            warnings.extend(_check_required_dirs(local_dir))
            elapsed = time.time() - start_time
            logger.info(
                "fetch_package reused local result file_count=%s warnings=%s elapsed=%.2fs",
                file_count,
                warnings,
                elapsed,
            )
            return build_response(
                status="success",
                step="fetch_package",
                env=request.env,
                version_date=request.version_date,
                message="本地目录已存在且包含文件，本次未重新下载",
                data={
                    "remote_dir": remote_dir,
                    "local_dir": str(local_dir),
                    "archive_file": str(archive_file),
                    "file_count": file_count,
                },
                warnings=warnings,
            )

        local_dir.mkdir(parents=True, exist_ok=True)

        try:
            ssh_manager = SSHManager(
                host=package_config["host"],
                port=int(package_config["port"]),
                username=package_config["username"],
                password=package_config["password"],
                connect_timeout=int(package_config["connect_timeout"]),
            )
            ssh_manager.connect()
            logger.info("ssh_connect success host=%s port=%s", package_config["host"], package_config["port"])
        except Exception as exc:
            logger.exception("ssh_connect failed")
            return _failed_response(request, "ssh_connect", "取包失败", exc)

        command_timeout = int(package_config["command_timeout"])
        remote_exists = _check_remote_dir(ssh_manager, remote_dir, command_timeout)
        logger.info("remote_dir check result=%s remote_dir=%s", remote_exists, remote_dir)
        if not remote_exists:
            return build_response(
                status="not_found",
                step="fetch_package",
                env=request.env,
                version_date=request.version_date,
                message="未发现当前版本升级包目录，等待下次触发",
                data={"remote_dir": remote_dir},
                warnings=warnings,
            )

        tar_result = ssh_manager.execute_command(
            f"cd {shlex.quote(remote_dir)} && tar -czf {shlex.quote(remote_archive)} .",
            timeout=command_timeout,
        )
        if tar_result.exit_status != 0:
            logger.error("remote_tar failed stdout=%s stderr=%s", tar_result.stdout, tar_result.stderr)
            return _failed_response(
                request,
                "remote_tar",
                "取包失败",
                RuntimeError(tar_result.stderr or tar_result.stdout or "远程压缩失败"),
            )
        logger.info("remote_tar success remote_archive=%s", remote_archive)

        try:
            ssh_manager.download_file(remote_archive, archive_file)
            logger.info("scp_download success archive_file=%s", archive_file)
        except Exception as exc:
            logger.exception("scp_download failed")
            return _failed_response(request, "scp_download", "取包失败", exc)
        finally:
            cleanup_warning = _cleanup_remote_archive(ssh_manager, remote_archive, command_timeout)
            if cleanup_warning:
                warnings.append(cleanup_warning)

        try:
            _extract_archive(archive_file, local_dir)
            logger.info("extract_archive success local_dir=%s", local_dir)
        except Exception as exc:
            logger.exception("extract_archive failed")
            return _failed_response(request, "extract_archive", "取包失败", exc, warnings)

        file_count = _count_files(local_dir)
        warnings.extend(_check_required_dirs(local_dir))
        elapsed = time.time() - start_time
        logger.info(
            "fetch_package success file_count=%s warnings=%s elapsed=%.2fs",
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
                "remote_dir": remote_dir,
                "local_dir": str(local_dir),
                "archive_file": str(archive_file),
                "file_count": file_count,
            },
            warnings=warnings,
        )

    except ConfigError as exc:
        logger.error("config error: %s", exc)
        return _failed_response(request, "config", "取包失败", exc, warnings)
    except Exception as exc:
        logger.exception("fetch_package unexpected failed")
        return _failed_response(request, "fetch_package", "取包失败", exc, warnings)
    finally:
        if ssh_manager is not None:
            ssh_manager.close()
        elapsed = time.time() - start_time
        logger.info("fetch_package end elapsed=%.2fs", elapsed)


def _build_remote_dir(package_config: dict[str, Any], year: str, version_date: str) -> str:
    package_name = package_config["package_name_template"].format(version_date=version_date)
    return f"{package_config['remote_root'].rstrip('/')}/{year}/{package_name}"


def _build_local_dir(package_config: dict[str, Any], version_date: str) -> Path:
    return Path(package_config["local_root"]) / version_date


def _build_remote_archive(package_config: dict[str, Any], env: str, version_date: str) -> str:
    return (
        f"{package_config['remote_temp_dir'].rstrip('/')}/"
        f"account_upgrade_{env}_{version_date}.tar.gz"
    )


def _has_local_files(local_dir: Path) -> bool:
    return local_dir.exists() and any(path.is_file() for path in local_dir.rglob("*"))


def _check_remote_dir(ssh_manager: SSHManager, remote_dir: str, timeout: int) -> bool:
    command = f"test -d {shlex.quote(remote_dir)} && echo OK || echo NOT_FOUND"
    result = ssh_manager.execute_command(command, timeout=timeout)
    return result.exit_status == 0 and "OK" in result.stdout.splitlines()


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


def _extract_archive(archive_file: Path, local_dir: Path) -> None:
    with tarfile.open(archive_file, "r:gz") as tar:
        _safe_extract(tar, local_dir)


def _safe_extract(tar: tarfile.TarFile, target_dir: Path) -> None:
    target_dir = target_dir.resolve()
    for member in tar.getmembers():
        member_path = (target_dir / member.name).resolve()
        # 保守处理归档路径，避免异常包内容解压到目标目录之外。
        if commonpath([str(target_dir), str(member_path)]) != str(target_dir):
            raise RuntimeError(f"压缩包包含非法路径: {member.name}")
    tar.extractall(target_dir)


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
) -> dict[str, Any]:
    return build_response(
        status="failed",
        step=step,
        env=request.env,
        version_date=request.version_date,
        message=message,
        warnings=warnings or [],
        error=str(exc),
    )
