"""Безопасный протокол smoke не пропускает произвольный вывод."""

import json
from email.message import Message
from unittest.mock import MagicMock
from urllib.error import HTTPError

import pytest

from scripts import container_smoke as smoke
from scripts.container_check import diagnostic_output, smoke_event


def test_http_failure_is_safe(capsys: pytest.CaptureFixture[str]) -> None:
    opener = MagicMock()
    opener.open.side_effect = HTTPError("secret", 403, "secret", Message(), None)
    with pytest.raises(RuntimeError):
        smoke.request_json(opener, "/health/live")
    output = capsys.readouterr()
    assert "secret" not in output.out + output.err
    assert '"category": "http"' in diagnostic_output(output.out)


def test_protocol_rejects_untrusted_values() -> None:
    event = {
        "protocol": "smoke-v1",
        "step": "ready",
        "method": "GET",
        "path": "/health/ready",
        "state": "failure",
        "category": "http",
        "status": 503,
    }
    assert smoke_event(json.dumps(event))
    for key in event:
        changed = {**event, key: "secret\nvalue"}
        assert not smoke_event(json.dumps(changed))
    assert not smoke_event(json.dumps({**event, "status": True}))
    assert "secret" not in diagnostic_output("secret\n" + json.dumps({**event, "token": "secret"}))
    assert diagnostic_output("process-root PID=12") == "process-root PID=12"
