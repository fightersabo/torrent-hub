from pathlib import Path
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    transmission_host: str = Field(default="localhost", env="TRANSMISSION_HOST")
    transmission_port: int = Field(default=9091, env="TRANSMISSION_PORT")
    transmission_username: str | None = Field(default=None, env="TRANSMISSION_USERNAME")
    transmission_password: str | None = Field(default=None, env="TRANSMISSION_PASSWORD")
    download_dir: Path = Field(default=Path("data/downloads").resolve(), env="DOWNLOAD_DIR")


settings = Settings()
settings.download_dir.mkdir(parents=True, exist_ok=True)
