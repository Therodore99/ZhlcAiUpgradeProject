from typing import Any, Optional


def build_response(
    *,
    status: str,
    step: str,
    system: Optional[str] = None,
    env: Optional[str] = None,
    version_date: Optional[str] = None,
    message: str,
    data: Optional[dict[str, Any]] = None,
    warnings: Optional[list[str]] = None,
    error: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "step": step,
        **({"system": system} if system is not None else {}),
        "env": env,
        "version_date": version_date,
        "message": message,
        "data": data or {},
        "warnings": warnings or [],
        "error": error,
    }
