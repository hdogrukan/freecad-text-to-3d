import json
import os
import threading
from datetime import datetime, timezone


class EventLogger:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def log(self, level: str, source: str, event: str, message: str, **data) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "source": source,
            "event": event,
            "message": message,
            "data": data,
        }
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def tail(self, limit: int = 120) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        limit = max(1, min(limit, 500))
        with self._lock:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-limit:]

        events = []
        for line in lines:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                events.append({
                    "ts": "",
                    "level": "warn",
                    "source": "logger",
                    "event": "parse_error",
                    "message": line.strip(),
                    "data": {},
                })
        return events
