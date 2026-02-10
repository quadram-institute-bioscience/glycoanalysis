"""FastAPI application assembly — WebSocket handler, lifespan, static mount."""

from __future__ import annotations

import asyncio
import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from .models import CompleteMessage, ErrorMessage, SessionStatus
from .routes import router, sessions, SESSIONS_ROOT

# --- Lifespan: session cleanup task ---

CLEANUP_INTERVAL = 600  # 10 minutes
SESSION_MAX_AGE = 7200  # 2 hours


async def _cleanup_loop() -> None:
    """Periodically remove expired session directories."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        now = time.time()
        try:
            if not SESSIONS_ROOT.is_dir():
                continue
            for d in SESSIONS_ROOT.iterdir():
                if not d.is_dir():
                    continue
                age = now - d.stat().st_mtime
                if age > SESSION_MAX_AGE:
                    shutil.rmtree(d, ignore_errors=True)
                    sessions.pop(d.name, None)
        except Exception:
            pass  # best-effort cleanup


@asynccontextmanager
async def lifespan(app: FastAPI):
    SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()


# --- App ---

app = FastAPI(
    title="glycoprep",
    version="0.1.0",
    root_path="/glycoprep",
    lifespan=lifespan,
)

app.include_router(router)


# --- WebSocket handler ---

@app.websocket("/ws/{sid}")
async def websocket_progress(ws: WebSocket, sid: str):
    """Stream pipeline progress events to the client."""
    await ws.accept()

    if sid not in sessions:
        await ws.send_json({"type": "error", "message": "Session not found"})
        await ws.close()
        return

    session = sessions[sid]
    queue: asyncio.Queue = session["queue"]

    try:
        while True:
            msg = await queue.get()

            # Serialize Pydantic model to dict
            data = msg.model_dump() if hasattr(msg, "model_dump") else msg

            await ws.send_json(data)

            # Terminal messages — update session state and stop
            if isinstance(msg, CompleteMessage):
                session["status"] = SessionStatus.done
                session["result"] = msg
                break
            if isinstance(msg, ErrorMessage):
                session["status"] = SessionStatus.error
                session["error"] = msg.message
                break

    except WebSocketDisconnect:
        pass


# --- Static files (built Svelte SPA) ---
# Mount AFTER api/ws routes so they take priority.

_STATIC_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _STATIC_DIR.is_dir():
    # Mount at /glycoprep for direct access (local dev without nginx)
    # and at / for behind-nginx access (nginx strips the /glycoprep/ prefix).
    app.mount("/glycoprep", StaticFiles(directory=str(_STATIC_DIR), html=True), name="spa-direct")
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="spa")
