from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WFMHUB2_", extra="ignore")

    home: Path = Path.cwd()
    host: str = "127.0.0.1"
    port: int = 8765

    @property
    def data_dir(self) -> Path:
        return self.home / "data"

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "db" / "wfmhub_app.sqlite3"

    @property
    def duckdb_path(self) -> Path:
        return self.data_dir / "db" / "wfmhub_analytics.duckdb"

    @property
    def inbox_dir(self) -> Path:
        return self.data_dir / "inbox"

    @property
    def lake_dir(self) -> Path:
        return self.data_dir / "lake"
