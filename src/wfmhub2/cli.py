import argparse

import uvicorn

from wfmhub2.core.settings import Settings
from wfmhub2.storage.duckdb import initialize as initialize_duckdb
from wfmhub2.storage.sqlite import initialize as initialize_sqlite


def init_storage(settings: Settings) -> None:
    settings.inbox_dir.mkdir(parents=True, exist_ok=True)
    settings.lake_dir.mkdir(parents=True, exist_ok=True)
    initialize_sqlite(settings.sqlite_path)
    initialize_duckdb(settings.duckdb_path)


def main() -> None:
    parser = argparse.ArgumentParser(prog="wfmhub2")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("serve")
    args = parser.parse_args()
    settings = Settings()

    if args.command == "init":
        init_storage(settings)
        print(f"Initialized WFMHub 2 at {settings.home}")
        return

    init_storage(settings)
    uvicorn.run("wfmhub2.api.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
