"""Helpers that insert TEST DATA rows directly. Never used by the app itself."""

from fortnite_coach.core.game_modes import AnalysisDepth, GameMode
from fortnite_coach.db.models import Report, SessionStatus, SkillScore
from fortnite_coach.db.repositories import session_repo


def add_test_report(db, fingerprint: str, scores: dict[str, tuple[float | None, int]], mode=GameMode.BOX_FIGHTS) -> int:
    """TEST DATA: create video + completed session + report with given {skill: (score, evidence)}."""
    vid = session_repo.upsert_video(
        db, session_repo.VideoInfo(path=f"C:/test/{fingerprint}.mp4", fingerprint=fingerprint, size_bytes=1000)
    )
    sid = session_repo.create_session(db, vid, mode, AnalysisDepth.STANDARD)
    with db.session() as s:
        rep = Report(session_id=sid, model="TEST-DATA", prompt_version="test", raw_json="{}")
        rep.skill_scores = [SkillScore(skill=k, score=v, evidence_count=e) for k, (v, e) in scores.items()]
        s.add(rep)
    session_repo.set_status(db, sid, SessionStatus.COMPLETED)
    return sid
