"""Cache of validated segment results: the same video + settings never costs a second request."""

from __future__ import annotations

import hashlib
import json

from fortnite_coach.db.engine import Database
from fortnite_coach.db.models import AnalysisCache


def make_key(**parts) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def get(db: Database, key: str) -> str | None:
    with db.session() as s:
        row = s.get(AnalysisCache, key)
        return row.result_json if row else None


def put(db: Database, key: str, result_json: str) -> None:
    with db.session() as s:
        row = s.get(AnalysisCache, key)
        if row is None:
            s.add(AnalysisCache(key=key, result_json=result_json))
        else:
            row.result_json = result_json
