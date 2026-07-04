import json
from pathlib import Path


BUNDLED_FILE = Path(__file__).parent / "static_data.json"
USER_FILE = Path.home() / ".orbo" / "static_data.json"


def load_static_data():
    file = USER_FILE if USER_FILE.exists() else BUNDLED_FILE

    with open(file, encoding="utf-8") as f:
        payload = json.load(f)

    data = payload["staticData"]

    for item in data:
        if "name" in item:
            item["name"] = item["name"].strip()
        if "description" in item:
            item["description"] = item["description"].strip()

    return data
