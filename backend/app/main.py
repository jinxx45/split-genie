from fastapi import FastAPI

app = FastAPI(title="Split Genie API")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "split-genie"}
