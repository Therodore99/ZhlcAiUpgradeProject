from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.health_api import router as health_router
from api.package_api import router as package_router
from core.response import build_response


app = FastAPI(title="Account Upgrade Server", version="0.1.0")

app.include_router(health_router)
app.include_router(package_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=build_response(
            status="failed",
            step="request_validation",
            message="请求参数校验失败",
            error=str(exc),
        ),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
