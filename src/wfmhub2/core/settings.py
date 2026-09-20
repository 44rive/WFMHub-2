from ipaddress import ip_address
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WFMHUB2_", extra="ignore")

    home: Path = Path.cwd()
    host: str = "127.0.0.1"
    port: int = 8765
    ducklake_extension: Path | None = None
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )

    @field_validator("host")
    @classmethod
    def host_must_be_loopback(cls, value: str) -> str:
        if value == "localhost":
            return value
        try:
            is_loopback = ip_address(value).is_loopback
        except ValueError as exc:
            raise ValueError("host must be a loopback IP address or localhost") from exc
        if not is_loopback:
            raise ValueError("host must be a loopback address")
        return value

    @field_validator("port")
    @classmethod
    def port_must_be_valid(cls, value: int) -> int:
        if not 0 <= value <= 65535:
            raise ValueError("port must be between 0 and 65535")
        return value

    @property
    def data_dir(self) -> Path:
        return self.home / "data"

    @property
    def control_db_path(self) -> Path:
        return self.data_dir / "control.sqlite"

    @property
    def inbox_dir(self) -> Path:
        return self.home / "Feed"

    @property
    def exports_dir(self) -> Path:
        return self.home / "Reports"

    @property
    def lake_dir(self) -> Path:
        return self.data_dir / "lake"

    @property
    def ducklake_catalog_path(self) -> Path:
        return self.lake_dir / "catalog.ducklake"

    @property
    def ducklake_data_path(self) -> Path:
        return self.lake_dir / "files"
