import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone


class ChatStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def list_chats(self) -> list[dict]:
        data = self._read()
        chats = data.get("chats", [])
        return sorted(
            (
                {
                    "id": chat["id"],
                    "title": chat.get("title") or "Untitled chat",
                    "created_at": chat.get("created_at"),
                    "updated_at": chat.get("updated_at"),
                    "message_count": len(chat.get("turns", [])),
                }
                for chat in chats
            ),
            key=lambda item: item.get("updated_at") or "",
            reverse=True,
        )

    def get_chat(self, chat_id: str) -> dict | None:
        data = self._read()
        return next((chat for chat in data.get("chats", []) if chat.get("id") == chat_id), None)

    def create_chat(self) -> dict:
        now = self._now()
        chat = {
            "id": uuid.uuid4().hex,
            "title": "Yeni chat",
            "created_at": now,
            "updated_at": now,
            "turns": [],
        }
        with self._lock:
            data = self._read()
            data.setdefault("chats", []).append(chat)
            self._write(data)
        return chat

    def add_turn(
        self,
        chat_id: str | None,
        user_message: str,
        description: str,
        python_code: str,
        freecad_result: dict,
    ) -> dict:
        with self._lock:
            data = self._read()
            chats = data.setdefault("chats", [])
            chat = next((item for item in chats if item.get("id") == chat_id), None)
            if chat is None:
                chat = self._new_chat_dict()
                chats.append(chat)

            turn = {
                "user": user_message,
                "description": description,
                "python_code": python_code,
                "freecad_result": freecad_result,
                "created_at": self._now(),
            }
            chat.setdefault("turns", []).append(turn)
            if not chat.get("title") or chat.get("title") == "Yeni chat":
                chat["title"] = self._make_title(user_message)
            chat["updated_at"] = turn["created_at"]
            self._write(data)
            return chat

    def clear(self) -> None:
        with self._lock:
            self._write({"chats": []})

    def to_openai_history(self, chat_id: str | None) -> list[dict]:
        if not chat_id:
            return []
        chat = self.get_chat(chat_id)
        if not chat:
            return []

        history = []
        for turn in chat.get("turns", []):
            history.append({"role": "user", "content": turn.get("user", "")})
            assistant_content = turn.get("description", "")
            code = turn.get("python_code", "")
            if code:
                assistant_content += f"\n\n```python\n{code}\n```"
            history.append({"role": "assistant", "content": assistant_content})
        return history

    def latest_python_code(self, chat_id: str | None) -> str:
        if not chat_id:
            return ""
        chat = self.get_chat(chat_id)
        if not chat:
            return ""
        for turn in reversed(chat.get("turns", [])):
            code = turn.get("python_code", "")
            if code:
                return code
        return ""

    def _new_chat_dict(self) -> dict:
        now = self._now()
        return {
            "id": uuid.uuid4().hex,
            "title": "Yeni chat",
            "created_at": now,
            "updated_at": now,
            "turns": [],
        }

    def _read(self) -> dict:
        if not os.path.exists(self.path):
            return {"chats": []}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("chats"), list):
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return {"chats": []}

    def _write(self, data: dict) -> None:
        directory = os.path.dirname(self.path)
        fd, tmp_path = tempfile.mkstemp(prefix=".chat_history_", suffix=".json", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _make_title(self, text: str) -> str:
        title = " ".join(text.split())
        if len(title) > 44:
            title = title[:41].rstrip() + "..."
        return title or "Yeni chat"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
