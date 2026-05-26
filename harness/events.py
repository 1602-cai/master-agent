"""Unified event model and event writer."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Event:
    """A single event emitted during a job."""

    __slots__ = ("ts", "type", "message", "payload")

    def __init__(self, event_type: str, message: str = "", **payload: Any):
        self.ts = datetime.now(timezone.utc).isoformat()
        self.type = event_type
        self.message = message
        self.payload = payload

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"ts": self.ts, "type": self.type}
        if self.message:
            d["message"] = self.message
        if self.payload:
            d["payload"] = self.payload
        return d


_EVENT_LOCKS: dict[Path, threading.Lock] = {}
_EVENT_NEXT_SEQ: dict[Path, int] = {}
_EVENT_LOCKS_GUARD = threading.Lock()


def _get_event_lock(path: Path) -> threading.Lock:
    resolved = path.resolve()
    with _EVENT_LOCKS_GUARD:
        if resolved not in _EVENT_LOCKS:
            _EVENT_LOCKS[resolved] = threading.Lock()
        return _EVENT_LOCKS[resolved]


class EventWriter:
    """Append-only JSONL event writer for a single job."""

    def __init__(self, job_dir: Path, on_event=None):
        self._path = job_dir / "events.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._on_event = on_event  # async callback(event_dict)
        self._lock = _get_event_lock(self._path)

    def write(self, event: Event) -> dict:
        d = event.to_dict()
        with self._lock:
            d["seq"] = self._reserve_seq_unlocked()
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
        # Fire async callback if set (for WebSocket broadcast)
        if self._on_event:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._on_event(d))
            except RuntimeError:
                pass
        return d

    def _reserve_seq_unlocked(self) -> int:
        resolved = self._path.resolve()
        next_seq = _EVENT_NEXT_SEQ.get(resolved)
        if next_seq is None:
            next_seq = self._next_seq_unlocked()
        _EVENT_NEXT_SEQ[resolved] = next_seq + 1
        return next_seq

    def read_all(self) -> list[dict]:
        if not self._path.exists():
            return []
        events = []
        with self._lock:
            with open(self._path, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    event.setdefault("seq", idx)
                    events.append(event)
        return events

    def _next_seq_unlocked(self) -> int:
        if not self._path.exists():
            return 1
        max_seq = 0
        with open(self._path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    max_seq = max(max_seq, int(event.get("seq", idx)))
                except (json.JSONDecodeError, TypeError, ValueError):
                    max_seq = max(max_seq, idx)
        return max_seq + 1
