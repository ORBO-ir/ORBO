import json
from pathlib import Path

from orbo.clients.static import StaticDataClient


USER_FILE = Path.home() / ".orbo" / "static_data.json"


def refresh_static_data():
    USER_FILE.parent.mkdir(parents=True, exist_ok=True)

    client = StaticDataClient()
    payload = client.get_static_data()

    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return USER_FILE
