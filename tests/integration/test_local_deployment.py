from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "scripts" / "launch_private_pilot.py"


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_json(url: str, *, timeout: float = 10) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=0.5) as response:  # noqa: S310
                return json.loads(response.read())
        except (ConnectionError, TimeoutError, URLError):
            time.sleep(0.05)
    raise AssertionError(f"service did not become reachable at {url}")


def _stop(process: subprocess.Popen[str]) -> tuple[str, str]:
    if process.poll() is None:
        if os.name == "nt":
            os.kill(process.pid, signal.CTRL_BREAK_EVENT)
        else:
            process.send_signal(signal.SIGTERM)
    stdout, stderr = process.communicate(timeout=8)
    return stdout, stderr


def _start_private_pilot(
    *,
    data_root: Path | str,
    credential_file: Path | str,
    frontend_dist: Path | str,
    port: int,
) -> subprocess.Popen[str]:
    command = [
        sys.executable,
        str(LAUNCHER),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--data-dir",
        str(data_root),
        "--credential-file",
        str(credential_file),
        "--frontend-dist",
        str(frontend_dist),
    ]
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    return subprocess.Popen(  # noqa: S603
        command,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "", "PYTHONUNBUFFERED": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
    )


def test_private_pilot_launches_ui_without_leaking_credential_and_stops_cleanly(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "workspace"
    credential_file = tmp_path / "runtime" / "workspace.credential"
    frontend_dist = tmp_path / "frontend"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text(
        "<!doctype html><title>Private Pilot</title><main>Oscillink Agent</main>",
        encoding="utf-8",
    )
    port = _free_port()
    command = [
        sys.executable,
        str(LAUNCHER),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--data-dir",
        str(data_root),
        "--credential-file",
        str(credential_file),
        "--frontend-dist",
        str(frontend_dist),
    ]
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process = subprocess.Popen(  # noqa: S603
        command,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "", "PYTHONUNBUFFERED": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
    )
    try:
        liveness = _wait_for_json(f"http://127.0.0.1:{port}/api/v1/health/live")
        credential = credential_file.read_text(encoding="utf-8").strip()
        with urlopen(f"http://127.0.0.1:{port}/", timeout=1) as response:  # noqa: S310
            html = response.read().decode()
    finally:
        stdout, stderr = _stop(process)

    assert liveness == {
        "schema_version": 1,
        "service": "oscillink-agent",
        "state": "alive",
    }
    assert "Oscillink Agent" in html
    assert len(credential) >= 32
    assert credential not in " ".join(command)
    assert credential not in stdout
    assert credential not in stderr
    assert process.returncode == 0
    assert not data_root.exists()


def test_restart_rotates_credential_and_preserves_workspace(tmp_path: Path) -> None:
    data_root = tmp_path / "workspace"
    credential_file = tmp_path / "runtime" / "workspace.credential"
    frontend_dist = tmp_path / "frontend"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("private pilot", encoding="utf-8")

    first_port = _free_port()
    first = _start_private_pilot(
        data_root=data_root,
        credential_file=credential_file,
        frontend_dist=frontend_dist,
        port=first_port,
    )
    try:
        _wait_for_json(f"http://127.0.0.1:{first_port}/api/v1/health/live")
        first_credential = credential_file.read_text(encoding="utf-8").strip()
        data_root.mkdir()
        marker = data_root / "preserved.marker"
        marker.write_text("canonical-state", encoding="utf-8")
    finally:
        _stop(first)

    second_port = _free_port()
    second = _start_private_pilot(
        data_root=data_root,
        credential_file=credential_file,
        frontend_dist=frontend_dist,
        port=second_port,
    )
    try:
        _wait_for_json(f"http://127.0.0.1:{second_port}/api/v1/health/live")
        second_credential = credential_file.read_text(encoding="utf-8").strip()
    finally:
        _stop(second)

    assert first.returncode == 0
    assert second.returncode == 0
    assert second_credential != first_credential
    assert marker.read_text(encoding="utf-8") == "canonical-state"


def test_non_loopback_bind_requires_explicit_authorization(tmp_path: Path) -> None:
    frontend_dist = tmp_path / "frontend"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("private pilot", encoding="utf-8")
    credential_file = tmp_path / "workspace.credential"
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(LAUNCHER),
            "--host",
            "0.0.0.0",
            "--port",
            str(_free_port()),
            "--data-dir",
            str(tmp_path / "workspace"),
            "--credential-file",
            str(credential_file),
            "--frontend-dist",
            str(frontend_dist),
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": ""},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 2
    assert "non-loopback host requires --allow-network-bind" in result.stderr
    assert not credential_file.exists()


def test_credential_file_cannot_enter_canonical_workspace(tmp_path: Path) -> None:
    data_root = tmp_path / "workspace"
    frontend_dist = tmp_path / "frontend"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("private pilot", encoding="utf-8")
    process = _start_private_pilot(
        data_root=data_root,
        credential_file=data_root / "workspace.credential",
        frontend_dist=frontend_dist,
        port=_free_port(),
    )
    try:
        stdout, stderr = process.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        _stop(process)
        pytest.fail("launcher accepted a credential file inside canonical workspace data")

    assert process.returncode == 2
    assert stdout == ""
    assert "credential file must be outside the data directory" in stderr
    assert not data_root.exists()


@pytest.mark.skipif(os.name != "nt", reason="MSYS path conversion is Windows-specific")
def test_launcher_normalizes_unconverted_msys_paths(tmp_path: Path) -> None:
    data_root = tmp_path / "workspace"
    credential_file = tmp_path / "runtime" / "workspace.credential"
    frontend_dist = tmp_path / "frontend"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("private pilot", encoding="utf-8")

    def msys(path: Path) -> str:
        native = path.resolve().as_posix()
        return f"/{native[0].lower()}{native[2:]}"

    port = _free_port()
    process = _start_private_pilot(
        data_root=msys(data_root),
        credential_file=msys(credential_file),
        frontend_dist=msys(frontend_dist),
        port=port,
    )
    try:
        assert _wait_for_json(f"http://127.0.0.1:{port}/api/v1/health/live") == {
            "schema_version": 1,
            "service": "oscillink-agent",
            "state": "alive",
        }
        assert credential_file.is_file()
    finally:
        stdout, stderr = _stop(process)

    assert process.returncode == 0
    assert credential_file.read_text(encoding="utf-8").strip() not in stdout + stderr
