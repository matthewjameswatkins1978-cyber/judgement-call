from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from judgement_call.contracts import ResumeRequest, RunResponse, StartRequest
from judgement_call.service import JudgementCallService

app = FastAPI(title="Judgement Call", version="0.1.0")

service = JudgementCallService()

# Mount static files if static/ directory exists
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def get_index() -> HTMLResponse:
    index_path = Path("static/index.html")
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Judgement Call</h1><p>Static index.html not found.</p>")


@app.post("/api/start", response_model=RunResponse)
async def api_start(request: StartRequest) -> RunResponse:
    try:
        response = service.start(request)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@app.post("/api/resume", response_model=RunResponse)
async def api_resume(request: ResumeRequest) -> RunResponse:
    try:
        response = service.resume(request)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
