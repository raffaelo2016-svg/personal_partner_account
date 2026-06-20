"""Export current OpenAPI schema to JSON file."""

import json
import sys
from pathlib import Path


def main() -> None:
    from app.main import app

    schema = app.openapi()
    output = Path("openapi.json")
    output.write_text(json.dumps(schema, indent=2, ensure_ascii=False))
    print(f"OpenAPI schema exported to {output} ({len(schema.get('paths', {}))} paths)")


if __name__ == "__main__":
    main()
    sys.exit(0)
