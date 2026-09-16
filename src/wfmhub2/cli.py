import argparse
from pathlib import Path

import uvicorn

from wfmhub2.core.settings import Settings
from wfmhub2.storage.lakehouse import initialize as initialize_lakehouse
from wfmhub2.storage.sqlite import initialize as initialize_sqlite


def init_storage(settings: Settings) -> None:
    settings.inbox_dir.mkdir(parents=True, exist_ok=True)
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    settings.ducklake_data_path.mkdir(parents=True, exist_ok=True)
    initialize_sqlite(settings.control_db_path)
    initialize_lakehouse(settings)


def _settings_from_args(args: argparse.Namespace) -> Settings:
    values: dict[str, object] = {}
    if args.home is not None:
        values["home"] = Path(args.home)
    if args.ducklake_extension is not None:
        values["ducklake_extension"] = Path(args.ducklake_extension)
    return Settings(**values)


def main() -> None:
    parser = argparse.ArgumentParser(prog="wfmhub2")
    parser.add_argument(
        "--home",
        default=None,
        help="Portable WFMHub home directory. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--ducklake-extension",
        default=None,
        help="Path to a locally bundled DuckLake extension for offline runtime.",
    )

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Initialize the local control DB and DuckLake")

    serve = sub.add_parser("serve", help="Start the local WFM engine API")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", default=None, type=int)

    args = parser.parse_args()
    settings = _settings_from_args(args)

    if args.command == "init":
        init_storage(settings)
        print(f"Initialized WFMHub 2 at {settings.home}")
        return

    init_storage(settings)
    uvicorn.run(
        "wfmhub2.api.main:app",
        host=args.host or settings.host,
        port=args.port or settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
