"""Export the OpenAPI schema to services/api/openapi.json."""

from __future__ import annotations

import json
import os
from pathlib import Path

# Importing the app validates configuration. The schema export only needs the
# route table, so force a storage backend that requires no external services.
os.environ["STORAGE_BACKEND"] = "local"

from avd_api.main import app  # noqa: E402


def main() -> None:
    schema = app.openapi()
    out = Path(__file__).resolve().parents[3] / "openapi.json"
    out.write_text(json.dumps(schema, indent=2))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
