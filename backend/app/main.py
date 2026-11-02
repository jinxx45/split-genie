import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from app.api import auth, splits
from app.config import settings
from app.observability import (
    configure_logging,
    elapsed_ms,
    enable_langsmith_if_configured,
    log_event,
)

configure_logging()
enable_langsmith_if_configured()

api_log = logging.getLogger("split_genie.api")

app = FastAPI(title="Split Rupya API")
app.include_router(auth.router)
app.include_router(splits.router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request, and tag it with an id that is also sent back to the browser,
    so a problem a user reports can be found in the logs."""
    request_id = request.headers.get("X-Request-ID", "")
    if not (request_id.replace("-", "").isalnum() and len(request_id) <= 64):
        # Missing, or unsafe to write into a log line (newlines could fake extra lines).
        request_id = uuid.uuid4().hex[:12]
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as error:  # a bug: anything expected is already an HTTPException
        log_event(
            api_log,
            logging.ERROR,
            "request failed",
            with_traceback=True,
            id=request_id,
            method=request.method,
            path=request.url.path,
            ms=elapsed_ms(started),
            error=type(error).__name__,
        )
        # Always JSON, with the id, so the app can show a reference that matches this log line.
        response = JSONResponse(
            status_code=500,
            content={"detail": f"Something went wrong on our side (ref {request_id}). Please try again."},
        )

    response.headers["X-Request-ID"] = request_id
    log_event(
        api_log,
        logging.INFO,
        "request",
        id=request_id,
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        ms=elapsed_ms(started),
    )
    return response


@app.exception_handler(RequestValidationError)
async def readable_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    """FastAPI's own checks (a missing form field, a wrong type) return a list of problems by
    default. Send the first one as a sentence, like every other error, so the app can show it."""
    first = error.errors()[0]
    where = ".".join(str(part) for part in first["loc"] if part not in ("body", "query", "path"))
    return JSONResponse(status_code=422, content={"detail": f"{where}: {first['msg']}" if where else first["msg"]})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "split-genie"}


# --- The React app, when it has been built into frontend_dir (the deployed app) ---
# Locally, Vite serves the frontend instead and this folder doesn't exist.

if settings.frontend_dir.is_dir():
    frontend = settings.frontend_dir.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def frontend_page(path: str) -> FileResponse:
        """A real file (script, style, icon) if there is one, otherwise the app's page. The app
        then shows the right screen for addresses like /split/abc itself."""
        if path.startswith("api/"):  # an API address that doesn't exist: not the app's page
            raise HTTPException(status_code=404, detail="Not found.")
        file = (frontend / path).resolve()
        if path and file.is_file() and frontend in file.parents:  # never serve files outside the folder
            # Built scripts and styles have a content hash in their names, so they can be cached for good.
            cache = "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
            return FileResponse(file, headers={"Cache-Control": cache})
        return FileResponse(frontend / "index.html", headers={"Cache-Control": "no-cache"})
