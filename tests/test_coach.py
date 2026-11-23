"""Ask the coach + 'what I struggle with'. Model answers are TEST DATA."""

import json

import pytest

from fortnite_coach.app import create_app
from fortnite_coach.config.paths import AppPaths
from fortnite_coach.db.engine import Database
from fortnite_coach.i18n.translator import get_translator
from fortnite_coach.workers.task import wait_all
from tests.fake_gemini import FakeClient

ANSWER = json.dumps({
    "answer": "TEST DATA: protect before you shoot", "key_points": ["TEST DATA cone first"],
    "drills": [{"name": "TEST DATA box drill", "how": "TEST DATA steps", "minutes": 10}],
    "search_queries": ["box fight wall take tutorial"]})


@pytest.fixture
def win(qtbot, tmp_path):
    from fortnite_coach.ui.main_window import MainWindow

    create_app([])
    paths = AppPaths(tmp_path / "h").ensure()
    db = Database(paths.database).init()
    client = FakeClient(responses=[ANSWER])
    w = MainWindow(db, paths, recording_source="test", client_factory=lambda k, t: client)
    qtbot.addWidget(w)
    w.set_language("en")
    yield w, client, qtbot
    wait_all()
    w._quitting = True
    db.close()
    get_translator().set_language("he")


def test_ask_coach_answers_with_drills_and_links(win):
    from tests.test_ui_analysis import connect

    w, client, qtbot = win
    page = w.pages["coach"]
    assert not page.ask_btn.isEnabled()  # no key yet
    connect(w, qtbot)
    page.notes.setPlainText("I lose box fights when they take my wall")
    page.question.setPlainText("How do I win box fights?")
    page.render()
    page.ask_btn.click()
    qtbot.waitUntil(lambda: not page.asking, timeout=10000)
    html = page.answer.text()
    assert "protect before you shoot" in html and "TEST DATA box drill" in html
    assert "tiktok.com/search?q=fortnite+box+fight+wall+take+tutorial" in html
    model, prompt, cfg = client.generate_calls[-1]
    assert "I lose box fights when they take my wall" in prompt      # their own words go to the coach
    assert w.settings.player_struggles.startswith("I lose box fights")
    from fortnite_coach.ai import usage_tracker

    assert usage_tracker.requests_today(w.db) == 1                  # counted in the daily limit
    from fortnite_coach.coaching import ask_coach

    assert ask_coach.load_history(w.db)[0].question == "How do I win box fights?"


def test_struggles_go_into_every_analysis_prompt():
    from fortnite_coach.coaching.prompt_builder import system_instruction
    from fortnite_coach.core.game_modes import GameMode

    text = system_instruction(GameMode.BOX_FIGHTS, [], "en", [], None, "I panic when pushed")
    assert "I panic when pushed" in text
    assert "struggle" not in system_instruction(GameMode.BOX_FIGHTS, [], "en", [], None, "")


def test_daily_limit_blocks_the_question(win):
    from tests.test_ui_analysis import connect

    w, client, qtbot = win
    connect(w, qtbot)
    w.settings.limits.max_requests_per_day = 0
    page = w.pages["coach"]
    page.question.setPlainText("anything")
    page.ask()
    qtbot.waitUntil(lambda: not page.asking, timeout=10000)
    assert "limit" in page.ask_status.text().lower() and not client.generate_calls[1:]
