from __future__ import annotations
import json
from pathlib import Path
from pydantic import BaseModel


class Staple(BaseModel):
    name: str
    quantity: str = ""


class StapleManager:
    def __init__(self, base_dir: Path | None = None):
        self._path = (base_dir or (Path.home() / ".grocery_lists")) / "staples.json"

    def list(self) -> list[Staple]:
        if not self._path.exists():
            return []
        return [Staple.model_validate(s) for s in json.loads(self._path.read_text())]

    def add(self, name: str, quantity: str = "") -> None:
        staples = self.list()
        if not any(s.name == name for s in staples):
            staples.append(Staple(name=name, quantity=quantity))
            self._save(staples)

    def remove(self, name: str) -> None:
        staples = [s for s in self.list() if s.name != name]
        self._save(staples)

    def _save(self, staples: list[Staple]) -> None:
        self._path.write_text(json.dumps([s.model_dump() for s in staples], indent=2))
