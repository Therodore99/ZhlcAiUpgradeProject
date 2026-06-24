from typing import Optional

from pydantic import BaseModel, Field


class BaseResponseSchema(BaseModel):
    status: str
    step: str
    env: Optional[str] = None
    version_date: Optional[str] = None
    message: str
    data: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: Optional[str] = None
