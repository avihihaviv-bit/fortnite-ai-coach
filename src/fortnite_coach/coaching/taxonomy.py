"""Fortnite evaluation taxonomy: what is judged per skill, and stable mistake codes.

Used for three things:
1. Skill pages show the criteria (bilingual).
2. The Gemini prompt (Phase 7) lists the criteria and the allowed mistake codes,
   so the AI classifies mistakes into a fixed vocabulary.
3. Stable codes let the coach count the SAME mistake across sessions.

Only things that can be seen in a gameplay recording are listed. Inputs that a
video cannot show (DPI, sensitivity, reaction time, real mouse accuracy, key binds)
are listed under NOT_MEASURABLE and must never be inferred.
"""

from __future__ import annotations

from dataclasses import dataclass

from fortnite_coach.core.skills import Skill


@dataclass(frozen=True)
class Criterion:
    code: str
    en: str
    he: str


@dataclass(frozen=True)
class MistakeType:
    code: str
    skill: Skill
    en: str
    he: str


def _c(code: str, en: str, he: str) -> Criterion:
    return Criterion(code, en, he)


CRITERIA: dict[Skill, tuple[Criterion, ...]] = {
    Skill.BUILDING: (
        _c("piece_placement", "Piece placement", "מיקום חלקים"),
        _c("protected_tunneling", "Protected tunneling", "טאנלינג מוגן"),
        _c("retakes", "Retakes", "ריטייקים"),
        _c("high_ground_retakes", "High-ground retakes", "ריטייק לגובה"),
        _c("tarping", "Tarping", "טארפינג"),
        _c("box_fighting", "Box fighting", "קרבות קופסה"),
        _c("defensive_building", "Defensive building", "בנייה הגנתית"),
        _c("building_under_pressure", "Building under pressure", "בנייה תחת לחץ"),
        _c("material_efficiency", "Efficient material usage", "שימוש יעיל בחומרים"),
    ),
    Skill.EDITING: (
        _c("wall_edits", "Wall edits", "עריכות קיר"),
        _c("cone_edits", "Cone edits", "עריכות קונוס"),
        _c("floor_edits", "Floor edits", "עריכות רצפה"),
        _c("multi_edits", "Double / triple / quad edits", "עריכות כפולות / משולשות / מרובעות"),
        _c("classics", "Mongraal-style classics", "קלאסיקות בסגנון Mongraal"),
        _c("edit_timing", "Edit timing", "תזמון עריכה"),
        _c("edit_and_shoot", "Edit-and-shoot", "עריכה וירייה"),
        _c("edit_reset", "Edit reset", "איפוס עריכה"),
        _c("edit_crosshair", "Crosshair placement while editing", "מיקום כוונת בזמן עריכה"),
        _c("editing_while_moving", "Editing while moving", "עריכה בתנועה"),
    ),
    Skill.PIECE_CONTROL: (
        _c("wall_floor_cone_control", "Wall, floor and cone control", "שליטה בקירות, רצפות וקונוסים"),
        _c("predicting_movement", "Predicting opponent movement", "חיזוי תנועת היריב"),
        _c("blocking_escapes", "Blocking escape routes", "חסימת נתיבי בריחה"),
        _c("pc_combinations", "Piece-control combinations", "קומבינציות שליטה בחלקים"),
        _c("right_hand_peeks", "Right-hand peeks", "פיקים לצד ימין"),
        _c("safe_damage", "Creating safe damage opportunities", "יצירת הזדמנויות נזק בטוחות"),
        _c("taking_walls", "Taking walls and controlling boxes", "לקיחת קירות ושליטה בקופסאות"),
    ),
    Skill.AIM: (
        _c("crosshair_placement", "Crosshair placement", "מיקום כוונת"),
        _c("tracking", "Tracking", "מעקב"),
        _c("flicking", "Flicking", "פליקים"),
        _c("shot_timing", "Shot timing", "תזמון יריות"),
        _c("shotgun_accuracy", "Shotgun accuracy (visible hits/misses)", "דיוק שוטגאן (פגיעות/החטאות נראות)"),
        _c("smg_tracking", "SMG tracking", "מעקב עם SMG"),
        _c("ar_accuracy", "AR accuracy", "דיוק עם רובה סער"),
        _c("damage_consistency", "Damage consistency (visible damage numbers)", "עקביות נזק (מספרי נזק נראים)"),
    ),
    Skill.MOVEMENT: (
        _c("movement_efficiency", "Movement efficiency", "יעילות תנועה"),
        _c("strafing", "Strafing", "סטרייפינג"),
        _c("jump_timing", "Jump timing", "תזמון קפיצות"),
        _c("peeking", "Peeking", "פיקים"),
        _c("dodging", "Dodging", "התחמקות"),
        _c("fight_positioning", "Positioning during fights", "מיקום בזמן קרב"),
    ),
    Skill.GAME_SENSE: (
        _c("rotations", "Rotations", "רוטציות"),
        _c("zone_awareness", "Zone awareness", "מודעות לאזור"),
        _c("storm_decisions", "Storm decisions", "החלטות סטורם"),
        _c("positioning", "Positioning", "מיקום"),
        _c("third_party_awareness", "Third-party awareness", "מודעות לצד שלישי"),
        _c("fight_selection", "Fight selection", "בחירת קרבות"),
        _c("push_or_disengage", "When to push and when to disengage", "מתי לדחוף ומתי להתנתק"),
        _c("resource_management", "Resource management (when visible)", "ניהול משאבים (כשנראה)"),
        _c("endgame", "Endgame decisions", "החלטות סוף משחק"),
        _c("opponent_awareness", "Awareness of opponents", "מודעות ליריבים"),
    ),
    Skill.FIGHT_EXECUTION: (
        _c("opening_moves", "Opening moves", "מהלכי פתיחה"),
        _c("protection", "Protection", "הגנה"),
        _c("creating_angles", "Creating angles", "יצירת זוויות"),
        _c("taking_shots", "Taking shots", "לקיחת יריות"),
        _c("following_up", "Following up", "המשכיות"),
        _c("resetting", "Resetting", "איפוס"),
        _c("recovering", "Recovering from mistakes", "התאוששות מטעויות"),
    ),
}


def _m(code: str, skill: Skill, en: str, he: str) -> MistakeType:
    return MistakeType(code, skill, en, he)


_B, _E, _P, _A, _M, _G, _F = (
    Skill.BUILDING, Skill.EDITING, Skill.PIECE_CONTROL, Skill.AIM, Skill.MOVEMENT, Skill.GAME_SENSE,
    Skill.FIGHT_EXECUTION,
)

MISTAKES: tuple[MistakeType, ...] = (
    # Building
    _m("BUILD_UNPROTECTED_SIDE", _B, "Built or moved with an open, unprotected side", "בנייה או תנועה עם צד פתוח ולא מוגן"),
    _m("BUILD_LATE_PROTECTION", _B, "Protection placed too late after taking damage", "הגנה שהונחה מאוחר מדי אחרי שנפגעת"),
    _m("BUILD_LOST_HIGH_GROUND", _B, "Lost height control to the opponent", "איבוד שליטה בגובה ליריב"),
    _m("BUILD_FAILED_RETAKE", _B, "Retake attempt without cover or with a predictable sequence", "ניסיון ריטייק בלי כיסוי או ברצף צפוי"),
    _m("BUILD_TUNNEL_GAP", _B, "Tunnel left a gap (missing cone/floor/wall)", "טאנל שהשאיר פתח (חסר קונוס/רצפה/קיר)"),
    _m("BUILD_OVERBUILD", _B, "Unnecessary building that wasted materials or time", "בנייה מיותרת שבזבזה חומרים או זמן"),
    _m("BUILD_PANIC_SPAM", _B, "Panic building under pressure instead of a structured sequence", "בנייה בפאניקה תחת לחץ במקום רצף מסודר"),
    # Editing
    _m("EDIT_FAILED", _E, "Edit failed or was confirmed incorrectly", "עריכה שנכשלה או אושרה לא נכון"),
    _m("EDIT_SLOW", _E, "Edit too slow for the situation", "עריכה איטית מדי למצב"),
    _m("EDIT_EXPOSED_AFTER", _E, "Stayed exposed after the edit (no reset / no shot)", "נשארת חשוף אחרי העריכה (בלי איפוס / בלי ירייה)"),
    _m("EDIT_REPEATED", _E, "Repeated the same edit; predictable", "אותה עריכה שוב ושוב, צפוי"),
    _m("EDIT_WRONG_TIMING", _E, "Edited when the opponent was ready / pre-aimed", "עריכה כשהיריב היה מוכן ומכוון מראש"),
    _m("EDIT_CROSSHAIR_OFF", _E, "Crosshair not on the opening when the edit completed", "הכוונת לא הייתה על הפתח כשהעריכה הושלמה"),
    # Piece control
    _m("PC_LOST_WALL", _P, "Lost a wall/piece the player could have claimed first", "איבוד קיר/חלק שהיה אפשר לתפוס קודם"),
    _m("PC_ATTACK_WITHOUT_PROTECTION", _P, "Tried to take a piece without protecting the other side", "ניסיון לקחת חלק בלי להגן על הצד השני"),
    _m("PC_OPPONENT_ESCAPED", _P, "Left an escape route open; opponent reset", "השארת נתיב בריחה פתוח, היריב התאפס"),
    _m("PC_UNSAFE_PEEK", _P, "Peeked from the exposed (left-hand) side", "פיק מהצד החשוף (שמאל)"),
    _m("PC_NO_FOLLOW_UP", _P, "Took control but did not convert it into damage", "השתלטות בלי להפוך אותה לנזק"),
    # Aim
    _m("AIM_CROSSHAIR_LOW", _A, "Crosshair placed away from head/chest height before the fight", "כוונת רחוקה מגובה ראש/חזה לפני הקרב"),
    _m("AIM_MISSED_OPEN_SHOT", _A, "Visible missed shot on an open target", "החטאה נראית על מטרה פתוחה"),
    _m("AIM_EARLY_SHOT", _A, "Shot fired before the crosshair was on target", "ירייה לפני שהכוונת הייתה על המטרה"),
    _m("AIM_LOST_TRACKING", _A, "Lost tracking on a moving target", "איבוד מעקב אחרי מטרה בתנועה"),
    _m("AIM_WRONG_WEAPON_RANGE", _A, "Used a weapon outside its effective range", "שימוש בנשק מחוץ לטווח היעיל שלו"),
    # Movement
    _m("MOVE_STATIC_IN_FIGHT", _M, "Stood still while exposed in a fight", "עמידה במקום כשהיית חשוף בקרב"),
    _m("MOVE_PREDICTABLE_STRAFE", _M, "Predictable strafe pattern", "דפוס סטרייף צפוי"),
    _m("MOVE_BAD_JUMP", _M, "Jump at the wrong moment made the player an easy target", "קפיצה ברגע הלא נכון הפכה אותך למטרה קלה"),
    _m("MOVE_INEFFICIENT_PATH", _M, "Inefficient movement path that cost time or exposure", "מסלול תנועה לא יעיל שעלה בזמן או בחשיפה"),
    # Game sense
    _m("GS_LATE_ROTATION", _G, "Rotated too late; forced into a bad position or storm", "רוטציה מאוחרת מדי, נכפה מיקום גרוע או סטורם"),
    _m("GS_BAD_FIGHT_SELECTION", _G, "Took a fight with a clear disadvantage", "כניסה לקרב עם חיסרון ברור"),
    _m("GS_THIRD_PARTIED", _G, "Got third-partied after ignoring nearby players", "צד שלישי תקף אחרי התעלמות משחקנים קרובים"),
    _m("GS_OVERPUSH", _G, "Pushed after losing the advantage (low health/materials)", "דחיפה אחרי איבוד היתרון (מעט חיים/חומרים)"),
    _m("GS_NO_DISENGAGE", _G, "Did not disengage when the fight was lost", "לא התנתקת כשהקרב כבר היה אבוד"),
    _m("GS_LOW_RESOURCES", _G, "Entered a fight with visibly low materials/heals", "כניסה לקרב עם מעט חומרים/ריפוי שנראה במסך"),
    _m("GS_ENDGAME_POSITION", _G, "Poor endgame position or layer choice", "מיקום או שכבה גרועים בסוף המשחק"),
    # Fight execution
    _m("FIGHT_NO_OPENING_PROTECTION", _F, "Opened the fight without protection", "פתיחת קרב בלי הגנה"),
    _m("FIGHT_NO_FOLLOW_UP", _F, "Landed damage but did not follow up", "גרמת נזק אבל לא המשכת"),
    _m("FIGHT_NO_RESET", _F, "Did not reset after taking damage", "לא התאפסת אחרי שנפגעת"),
)

NOT_MEASURABLE_EN = (
    "mouse DPI", "sensitivity", "reaction time", "true mouse accuracy", "key binds", "hardware input data",
)

MISTAKES_BY_CODE: dict[str, MistakeType] = {m.code: m for m in MISTAKES}


def criteria_for(skill: Skill) -> tuple[Criterion, ...]:
    return CRITERIA.get(skill, ())


def mistakes_for(skill: Skill) -> tuple[MistakeType, ...]:
    return tuple(m for m in MISTAKES if m.skill is skill)


def label(item: Criterion | MistakeType, language: str) -> str:
    return item.he if language == "he" else item.en
