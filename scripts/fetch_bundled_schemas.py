"""Fetch the 5 bundled PBI schemas from Microsoft CDN and save to _schemas/."""
import json
import urllib.request
from pathlib import Path

BASE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
DEST = Path(__file__).parent.parent / "src" / "tableau2pbir" / "validate" / "_schemas"

SCHEMAS = [
    ("semanticQuery/1.0.0/schema.json",                "semanticQuery-1.0.0.json"),
    ("semanticQuery/1.2.0/schema.json",                "semanticQuery-1.2.0.json"),
    ("semanticQuery/1.4.0/schema.json",                "semanticQuery-1.4.0.json"),
    ("filterConfiguration/1.1.0/schema-embedded.json", "filterConfiguration-1.1.0.json"),
    ("filterConfiguration/1.3.0/schema-embedded.json", "filterConfiguration-1.3.0.json"),
]

if __name__ == "__main__":
    for rel, filename in SCHEMAS:
        url = f"{BASE}/{rel}"
        print(f"Fetching {filename}...", end=" ")
        with urllib.request.urlopen(url) as r:
            content = r.read()
        parsed = json.loads(content)
        (DEST / filename).write_text(json.dumps(parsed, indent=2), encoding="utf-8")
        print("ok")
