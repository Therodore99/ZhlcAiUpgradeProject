from pydantic import BaseModel, Field, field_validator


class FetchPackageRequest(BaseModel):
    env: str = Field(..., min_length=1)
    year: str = Field(..., min_length=4, max_length=4)
    version_date: str = Field(..., min_length=8, max_length=8)
    force: bool = False
    debug: bool = False

    @field_validator("env")
    @classmethod
    def validate_env(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("env 不能为空")
        if not all(char.isalnum() or char in ("_", "-") for char in value):
            raise ValueError("env 只能包含字母、数字、下划线或中划线")
        return value

    @field_validator("year")
    @classmethod
    def validate_year(cls, value: str) -> str:
        if not value.isdigit() or len(value) != 4:
            raise ValueError("year 必须为 4 位数字")
        return value

    @field_validator("version_date")
    @classmethod
    def validate_version_date(cls, value: str) -> str:
        if not value.isdigit() or len(value) != 8:
            raise ValueError("version_date 必须为 8 位数字")
        return value
