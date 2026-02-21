from __future__ import annotations
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from fancy_grocery_list.models import GrocerySession, RawIngredient
from fancy_grocery_list.staples import StapleManager

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _make_id(name: str | None) -> str:
    date = _now().strftime("%Y-%m-%d")
    suffix = re.sub(r"[^\w-]", "", name.replace(" ", "-")).lower() if name else "session"
    return f"{date}-{suffix}"


class SessionManager:
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or (Path.home() / ".grocery_lists")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._current_pointer = self.base_dir / "current.json"

    def _session_path(self, session_id: str) -> Path:
        return self.base_dir / f"{session_id}.json"

    def new(self, name: str | None = None) -> GrocerySession:
        now = _now()
        session = GrocerySession(id=_make_id(name), name=name, created_at=now, updated_at=now)
        for staple in StapleManager(base_dir=self.base_dir).list():
            text = f"{staple.quantity} {staple.name}".strip()
            session.extra_items.append(RawIngredient(text=text, recipe_title="[staple]", recipe_url=""))
        self.save(session)
        self._set_current(session.id)
        return session

    def save(self, session: GrocerySession) -> None:
        session.updated_at = _now()
        self._session_path(session.id).write_text(session.model_dump_json(indent=2))

    def load(self, session_id: str) -> GrocerySession:
        path = self._session_path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"Session '{session_id}' not found.")
        return GrocerySession.model_validate_json(path.read_text())

    def load_current(self) -> GrocerySession:
        if not self._current_pointer.exists():
            raise FileNotFoundError("No active session. Run: grocery new")
        session_id = json.loads(self._current_pointer.read_text())["id"]
        return self.load(session_id)

    def _set_current(self, session_id: str) -> None:
        self._current_pointer.write_text(json.dumps({"id": session_id}))

    def finalize(self, session: GrocerySession, output_path: Path) -> None:
        session.finalized = True
        session.output_path = str(output_path)
        self.save(session)

    def list_sessions(self) -> list[GrocerySession]:
        sessions = []
        for path in sorted(self.base_dir.glob("*.json")):
            if path.name == "current.json":
                continue
            try:
                sessions.append(GrocerySession.model_validate_json(path.read_text()))
            except Exception:
                logger.warning("Could not read session file %s", path.name)
        return sessions

    def open_session(self, session_id: str) -> GrocerySession:
        session = self.load(session_id)
        session.finalized = False
        self.save(session)
        self._set_current(session.id)
        return session
