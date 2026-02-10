"""API routes for the glycoprep web interface."""

from __future__ import annotations

import asyncio
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from .models import SessionStatus, SessionResponse, UploadResponse
from .pipeline import run_pipeline

# --- Constants ---

ALLOWED_EXTENSIONS = {".xlsx", ".xls"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_SESSIONS = 50
DOWNLOAD_WHITELIST = {"matched_glycans.tsv", "unmatched_peaks.tsv"}

# --- Session storage ---

sessions: dict[str, dict] = {}
"""In-memory session store. Keys are session UUIDs."""

SESSIONS_ROOT = Path("/tmp/glycoprep")

router = APIRouter()

# Default bundled database path — try multiple locations to support both
# development (web/backend/routes.py → ../../data/db/) and Docker (/app/data/db/).
def _find_bundled_db() -> Path:
    candidates = [
        Path(__file__).resolve().parents[2] / "data" / "db" / "human_colon.xlsx",  # dev
        Path("/app/data/db/human_colon.xlsx"),  # docker
    ]
    for p in candidates:
        if p.is_file():
            return p
    return candidates[0]  # fallback — will error at runtime if missing

_BUNDLED_DB = _find_bundled_db()


def _validate_upload(file: UploadFile, label: str) -> None:
    """Validate an uploaded file's extension and size."""
    if file.filename is None:
        raise HTTPException(400, f"{label}: filename is required")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"{label}: unsupported file type '{ext}'. Use .xlsx or .xls")
    if file.size is not None and file.size > MAX_FILE_SIZE:
        raise HTTPException(400, f"{label}: file exceeds 50 MB limit")


async def _save_upload(file: UploadFile, dest: Path) -> None:
    """Read upload into *dest* in chunks."""
    total = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 256):
            total += len(chunk)
            if total > MAX_FILE_SIZE:
                dest.unlink(missing_ok=True)
                raise HTTPException(400, "Upload exceeds 50 MB limit")
            f.write(chunk)


# --- Upload ---

@router.post("/api/upload", response_model=UploadResponse)
async def upload(
    peaks_file: UploadFile = File(...),
    metadata_file: UploadFile = File(...),
    glycan_db_file: UploadFile | None = File(None),
    ppm_threshold: float = Form(100.0),
    skip_rows: int = Form(2),
    min_sn: float | None = Form(None),
):
    """Upload files and start the pipeline."""
    # Enforce session limit
    active = sum(1 for s in sessions.values() if s["status"] in (SessionStatus.pending, SessionStatus.running))
    if active >= MAX_SESSIONS:
        raise HTTPException(503, "Too many active sessions. Try again later.")

    # Validate uploads
    _validate_upload(peaks_file, "peaks_file")
    _validate_upload(metadata_file, "metadata_file")
    if glycan_db_file is not None and glycan_db_file.filename:
        _validate_upload(glycan_db_file, "glycan_db_file")

    # Create session directory
    sid = uuid.uuid4().hex
    session_dir = SESSIONS_ROOT / sid
    session_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded files
    peaks_path = session_dir / "peaks.xlsx"
    metadata_path = session_dir / "metadata.xlsx"
    await _save_upload(peaks_file, peaks_path)
    await _save_upload(metadata_file, metadata_path)

    # Use bundled DB or custom upload
    if glycan_db_file is not None and glycan_db_file.filename:
        db_path = session_dir / "glycan_db.xlsx"
        await _save_upload(glycan_db_file, db_path)
    else:
        db_path = _BUNDLED_DB

    # Register session
    queue: asyncio.Queue = asyncio.Queue()
    sessions[sid] = {
        "status": SessionStatus.running,
        "queue": queue,
        "result": None,
        "error": None,
        "dir": session_dir,
    }

    # Launch pipeline in background thread
    loop = asyncio.get_running_loop()
    t = threading.Thread(
        target=run_pipeline,
        kwargs=dict(
            session_id=sid,
            session_dir=session_dir,
            peaks_path=peaks_path,
            metadata_path=metadata_path,
            db_path=db_path,
            ppm_threshold=ppm_threshold,
            skip_rows=skip_rows,
            min_sn=min_sn,
            queue=queue,
            loop=loop,
        ),
        daemon=True,
    )
    t.start()

    return UploadResponse(
        session_id=sid,
        status=SessionStatus.running,
        ws_url=f"/ws/{sid}",
    )


# --- Session poll ---

@router.get("/api/session/{sid}", response_model=SessionResponse)
async def get_session(sid: str):
    """Poll session status (fallback when WebSocket disconnects)."""
    if sid in sessions:
        s = sessions[sid]
        return SessionResponse(
            session_id=sid,
            status=s["status"],
            result=s.get("result"),
            error=s.get("error"),
        )

    # Session not in memory — check if directory exists on disk (server restart)
    session_dir = SESSIONS_ROOT / sid
    if session_dir.is_dir():
        downloads = [
            f.name for f in session_dir.iterdir()
            if f.name in DOWNLOAD_WHITELIST
        ]
        if downloads:
            return SessionResponse(
                session_id=sid,
                status=SessionStatus.done,
                note="Session restored from disk. Full statistics unavailable — only downloads are available.",
            )

    raise HTTPException(404, "Session not found")


# --- Download ---

@router.get("/api/download/{sid}/{filename}")
async def download(sid: str, filename: str):
    """Download a result file from a session."""
    if filename not in DOWNLOAD_WHITELIST:
        raise HTTPException(400, f"File '{filename}' is not available for download")

    session_dir = SESSIONS_ROOT / sid
    file_path = session_dir / filename

    if not file_path.is_file():
        raise HTTPException(404, f"File '{filename}' not found for session")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="text/tab-separated-values",
    )
