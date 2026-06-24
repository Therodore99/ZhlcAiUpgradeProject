from fastapi import APIRouter

from core.response import build_response

router = APIRouter()


@router.get("/health")
def health_check():
    return build_response(
        status="success",
        step="health",
        message="服务正常",
        data={"service": "account_upgrade_server"},
    )
