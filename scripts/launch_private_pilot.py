"""Launch one bounded, private Oscillink Agent pilot process."""

from __future__ import annotations

import argparse
import ipaddress
import os
import re
import secrets
import signal
import sys
from pathlib import Path

import uvicorn

from oscillink_agent.api import create_app
from oscillink_agent.providers.config import build_chat_provider


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--credential-file", type=Path, required=True)
    parser.add_argument("--frontend-dist", type=Path, required=True)
    parser.add_argument(
        "--allow-network-bind",
        action="store_true",
        help="Permit an explicit non-loopback bind address.",
    )
    parser.add_argument(
        "--allowed-origin",
        action="append",
        default=[],
        help="Additional exact browser origin; repeat for multiple origins.",
    )
    parser.add_argument(
        "--trusted-host",
        action="append",
        default=[],
        help="Additional exact HTTP Host value; repeat for multiple hosts.",
    )
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if not 1 <= args.port <= 65535:
        raise ValueError("port must be in [1, 65535]")
    try:
        bind_address = ipaddress.ip_address(args.host)
    except ValueError as error:
        raise ValueError("host must be an explicit IP address") from error
    if not bind_address.is_loopback and not args.allow_network_bind:
        raise ValueError("non-loopback host requires --allow-network-bind")
    if not (args.frontend_dist / "index.html").is_file():
        raise ValueError("frontend distribution must contain index.html")
    data_root = args.data_dir.resolve()
    credential_file = args.credential_file.resolve()
    if credential_file == data_root or credential_file.is_relative_to(data_root):
        raise ValueError("credential file must be outside the data directory")


def _normalize_windows_path(path: Path) -> Path:
    """Accept Git Bash /c/... paths even when MSYS argument conversion is disabled."""

    if os.name != "nt":
        return path
    match = re.fullmatch(r"[\\/]([A-Za-z])([\\/].*)", str(path))
    if match is None:
        return path
    drive, remainder = match.groups()
    return Path(f"{drive.upper()}:{remainder}")


def _normalize_args(args: argparse.Namespace) -> None:
    args.data_dir = _normalize_windows_path(args.data_dir)
    args.credential_file = _normalize_windows_path(args.credential_file)
    args.frontend_dist = _normalize_windows_path(args.frontend_dist)


def _publish_credential(path: Path, credential: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{credential}\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    _normalize_args(args)
    try:
        _validate_args(args)
    except ValueError as error:
        parser.error(str(error))

    credential = secrets.token_urlsafe(32)
    _publish_credential(args.credential_file, credential)
    own_origin = f"http://{args.host}:{args.port}"
    trusted_hosts = tuple(dict.fromkeys([args.host, "localhost", *args.trusted_host]))
    allowed_origins = tuple(dict.fromkeys([own_origin, *args.allowed_origin]))
    provider = build_chat_provider(os.environ)
    app = create_app(
        data_root=args.data_dir,
        chat_provider=provider,
        workspace_credential=credential,
        allowed_origins=allowed_origins,
        trusted_hosts=trusted_hosts,
        static_root=args.frontend_dist,
    )
    print(f"Private pilot URL: {own_origin}", flush=True)
    print(f"Workspace credential file: {args.credential_file}", flush=True)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=args.host,
            port=args.port,
            access_log=False,
            log_level="warning",
        )
    )
    def request_shutdown(_signum: int, _frame: object) -> None:
        server.should_exit = True

    # Uvicorn restores and replays captured signals after graceful shutdown.
    # Installing a bounded launcher handler first prevents that replay from
    # re-terminating the already-clean process with a platform signal code.
    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)
    if os.name == "nt":
        signal.signal(signal.SIGBREAK, request_shutdown)
    server.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
