"""Generate the committed OpenAPI spec from the FastAPI app.

CI fails when the regenerated spec differs from `openapi/openapi.yaml`, so
the committed contract is always in sync with the code.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[4] / "openapi" / "openapi.yaml"


def main() -> None:
    from dhuan.api.app import create_app

    spec = dict(create_app().openapi())
    # FastAPI emits OpenAPI 3.1; the committed spec and our tooling
    # (Schemathesis, Redoc, codegen) use 3.0.x — see docs/adr/0005.
    spec["openapi"] = "3.0.3"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # minimal YAML emitter (json is valid YAML) with readability ordering
    OUT.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
