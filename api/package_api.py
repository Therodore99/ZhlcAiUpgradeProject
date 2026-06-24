from fastapi import APIRouter

from schemas.package_schema import FetchPackageRequest
from services.package_service import fetch_package

router = APIRouter()


@router.post("/fetch-package")
def fetch_package_api(request: FetchPackageRequest):
    return fetch_package(request)
