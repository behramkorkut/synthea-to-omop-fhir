"""POST the FHIR transaction bundle to a running FHIR server (HAPI).

HAPI takes a while to boot, so we first wait until it is ready (its /metadata
CapabilityStatement returns 200), then POST the bundle.

Run:  make fhir-server   # start HAPI (Docker)
      make fhir-export   # build data/fhir/bundle.json
      make fhir-push     # (this) waits for HAPI, then loads the bundle
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from ..config import settings


def _wait_ready(base: str, attempts: int = 40, delay: int = 3) -> None:
    """Poll the FHIR CapabilityStatement until the server answers."""
    meta = base.rstrip("/") + "/metadata"
    for i in range(1, attempts + 1):
        try:
            req = urllib.request.Request(
                meta, headers={"Accept": "application/fhir+json"}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                if r.status == 200:
                    print(f"FHIR server ready ({meta}).")
                    return
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        print(f"  waiting for the FHIR server to boot… ({i}/{attempts})")
        time.sleep(delay)
    raise RuntimeError(
        f"FHIR server not ready at {base} after ~{attempts * delay}s. "
        f"Is it started?  make fhir-server"
    )


def main() -> None:
    bundle_path = settings.fhir_out_dir / "bundle.json"
    if not bundle_path.exists():
        raise FileNotFoundError(
            f"{bundle_path} not found — run `make fhir-export` first."
        )

    _wait_ready(settings.fhir_base_url)

    data = bundle_path.read_bytes()
    req = urllib.request.Request(
        settings.fhir_base_url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/fhir+json",
            "Accept": "application/fhir+json",
        },
    )
    print(
        f"POSTing transaction bundle ({len(data) // 1024} KB) -> {settings.fhir_base_url}"
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = json.loads(resp.read())
            status = resp.status
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        print(f"HTTP {e.code} from the FHIR server. Server said:\n{detail[:1500]}")
        raise SystemExit(1) from e

    n = len(body.get("entry", []))
    print(f"HTTP {status} — {n} resources processed by the FHIR server.")
    print(f"Browse them at {settings.fhir_base_url}/Patient")


if __name__ == "__main__":
    main()
