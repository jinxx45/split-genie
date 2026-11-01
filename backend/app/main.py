import logging
import time
import uuid

from fastapi import FastAPI, Request

from app.observability import configure_logging, elapsed_ms, enable_langsmith_if_configured, log_event

configure_logging()
enable_langsmith_if_configured()

api_log = logging.getLogger("split_genie.api")

app = FastAPI(title="Split Genie API")


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
    except Exception as error:
        log_event(
            api_log,
            logging.ERROR,
            "request failed",
            id=request_id,
            method=request.method,
            path=request.url.path,
            ms=elapsed_ms(started),
            error=type(error).__name__,
        )
        raise

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


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "split-genie"}
