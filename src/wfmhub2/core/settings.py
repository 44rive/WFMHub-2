from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WFMHUB2_", extra="ignore")

    home: Path = Path.cwd()
    host: str = "127.0.0.1"
    port: int = 8765
    ducklake_extension: Path | None = None

    @property
    def data_dir(self) -> Path:
        return self.home / "data"

    @property
    def control_db_path(self) -> Path:
        return self.data_dir / "control.sqlite"

    @property
    def inbox_dir(self) -> Path:
        return self.data_dir / "inbox"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def lake_dir(self) -> Path:
        return self.data_dir / "lake"

    @property
    def ducklake_catalog_path(self) -> Path:
        return self.lake_dir / "catalog.ducklake"

    @property
    def ducklake_data_path(self) -> Path:
        return self.lake_dir / "files"
