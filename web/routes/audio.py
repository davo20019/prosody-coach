"""Serve recorded WAV files by UUID-based filename."""

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import RECORDINGS_DIR

router = APIRouter()

# Whitelist: 32 hex chars + .wav (matches uuid4().hex format).
_UUID_WAV = re.compile(r"^[0-9a-f]{32}\.wav$")


@router.get("/audio/{name}")
def get_audio(name: str) -> FileResponse:
    if not _UUID_WAV.match(name):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = Path(RECORDINGS_DIR) / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Recording not found")
    return FileResponse(path, media_type="audio/wav")
