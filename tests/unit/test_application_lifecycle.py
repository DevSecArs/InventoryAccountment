"""Закрытие ресурсов при штатном завершении приложения."""

import os
import signal
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from fastapi.testclient import TestClient

from app import http, postgresql


def test_lifespan_closes_database_on_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    close = MagicMock()
    monkeypatch.setattr(http, "close_database", close)
    with TestClient(http.create_app()) as client:
        assert client.get("/health/live").status_code == 200
        close.assert_not_called()
    close.assert_called_once_with()


def test_database_cleanup_disposes_pool_and_resets_factories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    postgresql.close_database()
    engine = MagicMock()
    create = MagicMock(return_value=engine)
    monkeypatch.setattr(postgresql, "create_engine", create)
    postgresql.get_engine()
    postgresql.get_session_factory()
    postgresql.close_database()
    engine.dispose.assert_called_once_with()
    assert postgresql.get_engine.cache_info().currsize == 0
    assert postgresql.get_session_factory.cache_info().currsize == 0
    postgresql.close_database()
    create.assert_called_once()


@pytest.mark.skipif(os.name != "posix", reason="SIGTERM требует POSIX")
def test_sigterm_finishes_inflight_request(tmp_path: Path) -> None:
    marker = tmp_path / "request-started"
    module = tmp_path / "shutdown_probe.py"
    module.write_text(
        "import asyncio\nfrom pathlib import Path\nfrom app.http import create_app\n"
        "app = create_app()\n@app.get('/slow')\nasync def slow():\n"
        f"    Path({str(marker)!r}).touch()\n"
        "    await asyncio.sleep(1)\n    return {'completed': True}\n",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(tmp_path), str(Path(__file__).resolve().parents[2]))
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        url = f"http://127.0.0.1:{listener.getsockname()[1]}"
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "shutdown_probe:app",
                "--fd",
                str(listener.fileno()),
                "--timeout-graceful-shutdown",
                "5",
            ],
            env=environment,
            pass_fds=(listener.fileno(),),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            deadline = time.monotonic() + 15
            while True:
                try:
                    with urlopen(url + "/health/live", timeout=0.2) as response:
                        assert response.status == 200
                    break
                except (URLError, TimeoutError):
                    assert process.poll() is None and time.monotonic() < deadline
                    time.sleep(0.05)

            def request() -> bytes:
                with urlopen(url + "/slow", timeout=10) as response:
                    body = response.read()
                    assert isinstance(body, bytes)
                    return body

            with ThreadPoolExecutor(max_workers=1) as executor:
                result = executor.submit(request)
                while not marker.exists():
                    assert time.monotonic() < deadline
                    time.sleep(0.01)
                process.send_signal(signal.SIGTERM)
                assert result.result(timeout=10) == b'{"completed":true}'
            output, _ = process.communicate(timeout=10)
            assert process.returncode in (0, -signal.SIGTERM), output
            assert "Application shutdown complete." in output
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
