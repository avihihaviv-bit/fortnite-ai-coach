from __future__ import annotations

from sqlalchemy import select

from fortnite_coach.db.engine import Database
from fortnite_coach.db.models import PlayerProfile


def get_or_create_profile(db: Database) -> PlayerProfile:
    with db.session() as s:
        profile = s.scalars(select(PlayerProfile).limit(1)).first()
        if profile is None:
            profile = PlayerProfile()
            s.add(profile)
            s.flush()
        return profile


def update_profile(db: Database, *, display_name: str | None = None) -> PlayerProfile:
    with db.session() as s:
        profile = s.scalars(select(PlayerProfile).limit(1)).first() or PlayerProfile()
        s.add(profile)
        if display_name is not None:
            profile.display_name = display_name.strip()[:64]
        s.flush()
        return profile
