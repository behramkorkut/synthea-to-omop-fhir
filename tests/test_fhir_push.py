"""Tests du push FHIR vers HAPI (fhir/push.py) — réseau entièrement mocké.

Le module utilise ``urllib.request`` (pas httpx) : on remplace ``urlopen`` par
des réponses factices pour tester le polling ``/metadata`` et le POST du bundle
sans serveur FHIR. ``delay=0`` rend les retries instantanés (pas besoin de
patcher ``time.sleep``).
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from synthea_omop_fhir.config import settings
from synthea_omop_fhir.fhir import push


class _FakeResponse:
    """Réponse factice d'urlopen : context manager avec .status et .read()."""

    def __init__(self, status: int = 200, payload: bytes = b"{}") -> None:
        self.status = status
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_wait_ready_returns_on_first_200(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def ok(req: urllib.request.Request, timeout: float) -> _FakeResponse:
        calls.append(req.full_url)
        return _FakeResponse(200)

    monkeypatch.setattr(urllib.request, "urlopen", ok)
    push._wait_ready("http://hapi.example/fhir", attempts=3, delay=0)
    assert calls == ["http://hapi.example/fhir/metadata"]


def test_wait_ready_retries_until_200(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"n": 0}

    def flaky(req: urllib.request.Request, timeout: float) -> _FakeResponse:
        state["n"] += 1
        if state["n"] < 3:
            raise urllib.error.URLError("connexion refusée")
        return _FakeResponse(200)

    monkeypatch.setattr(urllib.request, "urlopen", flaky)
    # trailing slash : l'URL doit être normalisée, pas "//metadata"
    push._wait_ready("http://hapi.example/fhir/", attempts=5, delay=0)
    assert state["n"] == 3


def test_wait_ready_raises_after_all_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    def down(req: urllib.request.Request, timeout: float) -> _FakeResponse:
        raise urllib.error.URLError("down")

    monkeypatch.setattr(urllib.request, "urlopen", down)
    with pytest.raises(RuntimeError, match="not ready"):
        push._wait_ready("http://x", attempts=2, delay=0)


def test_main_missing_bundle_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "fhir_out_dir", tmp_path)
    with pytest.raises(FileNotFoundError, match="fhir-export"):
        push.main()


def test_main_posts_bundle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle.json"
    bundle.write_text(json.dumps({"resourceType": "Bundle", "entry": [{}, {}]}))
    monkeypatch.setattr(settings, "fhir_out_dir", tmp_path)
    monkeypatch.setattr(settings, "fhir_base_url", "http://hapi.example/fhir")

    posted: dict[str, bytes] = {}

    def fake_urlopen(req: urllib.request.Request, timeout: float) -> _FakeResponse:
        if req.full_url.endswith("/metadata"):
            return _FakeResponse(200)
        posted["data"] = req.data or b""
        return _FakeResponse(200, json.dumps({"entry": [{}, {}, {}]}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    push.main()
    out = capsys.readouterr().out
    assert "3 resources processed" in out
    # Le corps POSTé est bien le contenu brut du bundle exporté.
    assert posted["data"] == bundle.read_bytes()


def test_main_http_error_exits_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle.json"
    bundle.write_text(json.dumps({"resourceType": "Bundle"}))
    monkeypatch.setattr(settings, "fhir_out_dir", tmp_path)
    monkeypatch.setattr(settings, "fhir_base_url", "http://hapi.example/fhir")

    def fake_urlopen(req: urllib.request.Request, timeout: float) -> _FakeResponse:
        if req.full_url.endswith("/metadata"):
            return _FakeResponse(200)
        raise urllib.error.HTTPError(
            req.full_url,
            422,
            "Unprocessable",
            hdrs=None,
            fp=io.BytesIO(b'{"issue": []}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(SystemExit) as exc:
        push.main()
    assert exc.value.code == 1
    assert "HTTP 422" in capsys.readouterr().out
