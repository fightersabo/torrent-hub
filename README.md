# Torrent Hub

A modern web UI for running Transmission on your server. Add magnet links or `.torrent` files, monitor speeds and progress, then stream or download completed videos with English and Arabic subtitle support.

## Features
- Add torrents via magnet link or `.torrent` upload directly into Transmission
- Real-time status including progress, ETA, download/upload speeds, and size
- Stream completed video files with HTTP range support
- Download the finished video with a single click
- Subtitle tracks served in WebVTT (auto-converts `.srt`), with language detection for English/Arabic
- FastAPI backend + lightweight static UI

## Quick install (Ubuntu 24.04)
```bash
bash install.sh
```
This installs Transmission, creates a virtualenv, and installs Python dependencies. Transmission RPC is left open on port `9091` for the local host; adjust `/etc/transmission-daemon/settings.json` for stricter access if needed.

## Running the app
```bash
source .venv/bin/activate
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```
Open `http://localhost:8000` for the UI.

### Environment overrides
| Variable | Description | Default |
| --- | --- | --- |
| `TRANSMISSION_HOST` | Transmission RPC host | `localhost` |
| `TRANSMISSION_PORT` | Transmission RPC port | `9091` |
| `TRANSMISSION_USERNAME` | RPC username (if auth enabled) | unset |
| `TRANSMISSION_PASSWORD` | RPC password | unset |
| `DOWNLOAD_DIR` | Download directory used by Transmission | `data/downloads` |

## Subtitle support
- Subtitle files with `.srt` or `.vtt` extensions are exposed to the player.
- Names containing `en/eng/english` or `ar/ara/arabic` are labeled accordingly.
- `.srt` files are converted to WebVTT on the fly for browser playback.

## Project layout
```
backend/           FastAPI app and Transmission integration
web/               Static UI served by FastAPI
requirements.txt   Python dependencies
install.sh         One-click setup script for Ubuntu 24.04
```
