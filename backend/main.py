from __future__ import annotations

import base64
import mimetypes
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from transmission_rpc import Client, TransmissionError

from .config import settings

mimetypes.add_type("video/x-matroska", ".mkv")

app = FastAPI(title="Torrent Hub", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TransmissionManager:
    def __init__(
        self,
        host: str,
        port: int,
        username: Optional[str] = None,
        password: Optional[str] = None,
        download_dir: Path = settings.download_dir,
    ) -> None:
        self.download_dir = download_dir
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.client = Client(
            host=host,
            port=port,
            username=username,
            password=password,
        )

    def add_magnet(self, magnet_link: str):
        if not magnet_link.startswith("magnet:"):
            raise HTTPException(status_code=400, detail="Invalid magnet link")
        try:
            torrent = self.client.add_torrent(magnet_link, download_dir=str(self.download_dir))
        except TransmissionError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"id": torrent.id, "name": torrent.name}

    def add_torrent_file(self, path: Path):
        try:
            torrent = self.client.add_torrent(str(path), download_dir=str(self.download_dir))
        except TransmissionError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"id": torrent.id, "name": torrent.name}

    def list_torrents(self) -> List[Dict]:
        torrents = self.client.get_torrents()
        return [self._serialize_torrent(t) for t in torrents]

    def _serialize_torrent(self, torrent) -> Dict:
        files = torrent.files()
        video_files = [f for f in files if Path(f["name"]).suffix.lower() in VIDEO_EXTENSIONS]
        subtitle_files = [f for f in files if Path(f["name"]).suffix.lower() in SUBTITLE_EXTENSIONS]
        primary_video = video_files[0]["name"] if video_files else None

        return {
            "id": torrent.id,
            "name": torrent.name,
            "status": torrent.status,
            "progress": round(torrent.progress, 2),
            "downloadRate": torrent.rateDownload,
            "uploadRate": torrent.rateUpload,
            "eta": torrent.format_eta(),
            "isFinished": torrent.isFinished,
            "totalSize": torrent.totalSize,
            "primaryVideo": primary_video,
            "files": {
                "videos": [self._build_file_info(torrent.id, f["name"]) for f in video_files],
                "subtitles": [self._build_subtitle_info(torrent.id, f["name"]) for f in subtitle_files],
            },
        }

    def _build_file_info(self, torrent_id: int, relative_path: str) -> Dict:
        stream_url = f"/stream/{torrent_id}?file={_encode_path(relative_path)}"
        download_url = f"/download/{torrent_id}?file={_encode_path(relative_path)}"
        return {
            "path": relative_path,
            "streamUrl": stream_url,
            "downloadUrl": download_url,
        }

    def _build_subtitle_info(self, torrent_id: int, relative_path: str) -> Dict:
        lang = _guess_language(relative_path)
        subtitle_url = f"/subtitle/{torrent_id}?file={_encode_path(relative_path)}"
        return {
            "path": relative_path,
            "language": lang,
            "url": subtitle_url,
        }


def get_manager() -> TransmissionManager:
    return TransmissionManager(
        host=settings.transmission_host,
        port=settings.transmission_port,
        username=settings.transmission_username,
        password=settings.transmission_password,
        download_dir=settings.download_dir,
    )


@app.post("/torrents/magnet")
def add_magnet_link(payload: Dict[str, str], manager: TransmissionManager = Depends(get_manager)):
    magnet = payload.get("magnet")
    if not magnet:
        raise HTTPException(status_code=400, detail="Missing magnet link")
    return manager.add_magnet(magnet)


@app.post("/torrents/upload")
def upload_torrent(
    torrent: UploadFile = File(...),
    manager: TransmissionManager = Depends(get_manager),
):
    suffix = Path(torrent.filename or "").suffix.lower()
    if suffix not in {".torrent"}:
        raise HTTPException(status_code=400, detail="Only .torrent files are accepted")

    temp_path = settings.download_dir / f"upload-{os.getpid()}-{torrent.filename}"
    with temp_path.open("wb") as f:
        f.write(torrent.file.read())

    try:
        return manager.add_torrent_file(temp_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


@app.get("/torrents")
def list_torrents(manager: TransmissionManager = Depends(get_manager)):
    return {"torrents": manager.list_torrents()}


def _safe_file_path(relative_path: str) -> Path:
    decoded = _decode_path(relative_path)
    path = (settings.download_dir / decoded).resolve()
    if settings.download_dir not in path.parents and path != settings.download_dir:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return path


@app.get("/download/{torrent_id}")
def download_file(torrent_id: int, file: str):  # noqa: A002
    path = _safe_file_path(file)
    return FileResponse(path, filename=Path(file).name)


@app.get("/stream/{torrent_id}")
def stream_file(torrent_id: int, file: str, range: Optional[str] = None):  # noqa: A002
    path = _safe_file_path(file)
    media_type, _ = mimetypes.guess_type(str(path))
    media_type = media_type or "application/octet-stream"

    def iter_file(start: int, end: int, file_path: Path) -> Iterable[bytes]:
        with file_path.open("rb") as f:
            f.seek(start)
            bytes_left = end - start + 1
            chunk_size = 1024 * 1024
            while bytes_left > 0:
                read_size = min(chunk_size, bytes_left)
                data = f.read(read_size)
                if not data:
                    break
                bytes_left -= len(data)
                yield data

    file_size = path.stat().st_size
    if range:
        match = re.match(r"bytes=(\d+)-(\d*)", range)
        if match:
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else file_size - 1
            end = min(end, file_size - 1)
            if start >= file_size:
                raise HTTPException(status_code=416, detail="Range Not Satisfiable")
            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(end - start + 1),
            }
            return StreamingResponse(
                iter_file(start, end, path),
                status_code=206,
                media_type=media_type,
                headers=headers,
            )
    headers = {"Accept-Ranges": "bytes"}
    return StreamingResponse(path.open("rb"), media_type=media_type, headers=headers)


@app.get("/subtitle/{torrent_id}")
def subtitle_file(torrent_id: int, file: str):  # noqa: A002
    path = _safe_file_path(file)
    if path.suffix.lower() == ".srt":
        converted = _srt_to_vtt(path)
        return StreamingResponse(converted, media_type="text/vtt")
    return FileResponse(path, media_type="text/vtt")


def _srt_to_vtt(path: Path):
    yield "WEBVTT\n\n"
    pattern = re.compile(r"(\d{2}:\d{2}:\d{2}),(\d{3})")
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            yield pattern.sub(r"\1.\2", line)


@app.get("/health")
def health_check():
    return {"status": "ok"}


VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}
SUBTITLE_EXTENSIONS = {".srt", ".vtt"}


def _encode_path(path: str) -> str:
    return base64.urlsafe_b64encode(path.encode()).decode()


def _decode_path(encoded: str) -> str:
    try:
        return base64.urlsafe_b64decode(encoded.encode()).decode()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Invalid path") from exc


def _guess_language(path: str) -> str:
    name = Path(path).stem.lower()
    if any(tag in name for tag in ["en", "eng", "english"]):
        return "en"
    if any(tag in name for tag in ["ar", "ara", "arabic"]):
        return "ar"
    return "unknown"


STATIC_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
