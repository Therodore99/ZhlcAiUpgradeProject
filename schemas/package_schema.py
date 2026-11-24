from typing import Literal, Optional

from pydantic import BaseModel, Field


class FetchPackageRequest(BaseModel):
    system: Literal["legacy_account", "bus", "xinchuang_account"] = "legacy_account"
    env: Literal["uat1", "uat2"]
    year: Optional[str] = Field(None, pattern=r"^[0-9]{4}$")
    version_date: str = Field(pattern=r"^[0-9]{8}$")
    force: bool = False
    debug: bool = False

