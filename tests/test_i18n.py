import json

from fortnite_coach.config.paths import resource_path
from fortnite_coach.core.game_modes import AnalysisDepth, GameMode
from fortnite_coach.core.skills import Skill
from fortnite_coach.i18n.translator import Translator


def _catalog(lang):
    return json.loads(resource_path(f"i18n/{lang}.json").read_text(encoding="utf-8"))


def test_catalogs_have_same_keys():
    assert _catalog("en").keys() == _catalog("he").keys()


def test_all_enums_translated():
    en = _catalog("en")
    for e in (*Skill, *GameMode, *AnalysisDepth):
        assert e.i18n_key in en


def test_switch_language_and_rtl():
    t = Translator("en")
    seen = []
    t.on_change(seen.append)
    assert not t.is_rtl
    assert t.tr("nav.dashboard") == "Dashboard"
    t.set_language("he")
    assert t.is_rtl and seen == ["he"]
    assert t.tr("nav.dashboard") == "לוח בקרה"


def test_missing_key_returns_key():
    assert Translator("he").tr("does.not.exist") == "does.not.exist"
