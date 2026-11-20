"""Exercise catalog (bilingual). Each exercise targets specific mistake codes from taxonomy.py.

No Fortnite island codes are listed on purpose: codes change and cannot be verified here.
Each exercise names a map TYPE; the player searches Creative/Discover for a current map of that type.
"""

from __future__ import annotations

from dataclasses import dataclass

from fortnite_coach.core.skills import Skill


@dataclass(frozen=True)
class T:  # bilingual text
    en: str
    he: str

    def get(self, lang: str) -> str:
        return self.he if lang == "he" else self.en


@dataclass(frozen=True)
class ExerciseTemplate:
    id: str
    category: str      # warm_up, mechanics, editing, building, piece_control, aim, realistic_1v1, box_fights, zone_wars, game_sense
    skill: Skill
    difficulty: str    # easy | medium | hard
    duration_min: int
    name: T
    goal: T
    instructions: T
    success: T
    level_up: T
    map_type: T
    targets: tuple[str, ...] = ()  # mistake codes this exercise fixes


B, E, P, A, M, G, F = (Skill.BUILDING, Skill.EDITING, Skill.PIECE_CONTROL, Skill.AIM, Skill.MOVEMENT,
                       Skill.GAME_SENSE, Skill.FIGHT_EXECUTION)

CATALOG: tuple[ExerciseTemplate, ...] = (
    # ---------------- warm-up ----------------
    ExerciseTemplate(
        "warmup_mechanics", "warm_up", E, "easy", 10,
        T("Mechanics warm-up", "חימום מכניקה"),
        T("Wake up hands and crosshair before anything else.", "להעיר ידיים וכוונת לפני כל דבר אחר."),
        T("3 min free build (ramps, walls, cones in all directions). 3 min edit course at a calm pace with zero failed edits. "
          "4 min aim map: flicks then tracking.",
          "3 דקות בנייה חופשית (רמפות, קירות, קונוסים לכל הכיוונים). 3 דקות מסלול עריכות בקצב רגוע בלי אף עריכה שנכשלה. "
          "4 דקות מפת כיוון: פליקים ואז מעקב."),
        T("All three parts done without rushing; no failed edits in the edit part.",
          "שלושת החלקים בוצעו בלי למהר; אין עריכות שנכשלו בחלק העריכות."),
        T("When it feels easy: same 10 minutes at a faster pace.", "כשזה מרגיש קל: אותן 10 דקות בקצב מהיר יותר."),
        T("Free build island + edit course + aim trainer", "אי בנייה חופשית + מסלול עריכות + מפת אימון כיוון")),
    # ---------------- editing ----------------
    ExerciseTemplate(
        "edit_reset_drill", "editing", E, "easy", 10,
        T("Edit, shoot, reset", "עריכה, ירייה, איפוס"),
        T("Never stay inside an open edit.", "אף פעם לא להישאר בתוך עריכה פתוחה."),
        T("On an edit course: every edit = open, take one shot at the target spot, then immediately reset the wall. "
          "Say 'reset' out loud for the first 5 minutes until it is automatic.",
          "במסלול עריכות: כל עריכה = פתיחה, ירייה אחת לנקודת המטרה, ומיד איפוס הקיר. "
          "תגיד 'איפוס' בקול ב-5 הדקות הראשונות עד שזה נהיה אוטומטי."),
        T("20 edits in a row with a reset after every one.", "20 עריכות ברצף עם איפוס אחרי כל אחת."),
        T("Add a moving bot or a friend shooting at the edit.", "הוסף בוט זז או חבר שיורה על העריכה."),
        T("Edit course map", "מפת מסלול עריכות"),
        ("EDIT_EXPOSED_AFTER", "EDIT_REPEATED")),
    ExerciseTemplate(
        "edit_speed_accuracy", "editing", E, "medium", 12,
        T("Edit accuracy ladder", "סולם דיוק עריכות"),
        T("Faster edits without failed confirms.", "עריכות מהירות יותר בלי אישורים שנכשלים."),
        T("Run the same edit course 5 times. Run 1 slow and perfect, then speed up each run. "
          "Restart the run after any failed edit.",
          "עבור על אותו מסלול עריכות 5 פעמים. ריצה 1 איטית ומושלמת, ואז להאיץ בכל ריצה. "
          "להתחיל מחדש אחרי כל עריכה שנכשלה."),
        T("A full run with zero failed edits at a faster time than run 1.", "ריצה מלאה בלי עריכות שנכשלו, בזמן מהיר מריצה 1."),
        T("Switch to double/triple edit patterns.", "לעבור לתבניות של עריכות כפולות/משולשות."),
        T("Edit course map", "מפת מסלול עריכות"),
        ("EDIT_FAILED", "EDIT_SLOW")),
    ExerciseTemplate(
        "edit_crosshair_preaim", "editing", E, "medium", 10,
        T("Pre-aimed edits", "עריכות עם כיוון מראש"),
        T("Crosshair is already on the opening when the edit completes.", "הכוונת כבר על הפתח כשהעריכה מסתיימת."),
        T("Place a target (bot or prop) behind a wall. Before each edit, put the crosshair at chest height where the "
          "opening will be, then edit and shoot without moving the mouse.",
          "שים מטרה (בוט או חפץ) מאחורי קיר. לפני כל עריכה, שים את הכוונת בגובה חזה איפה שיהיה הפתח, "
          "ואז ערוך וירה בלי להזיז את העכבר."),
        T("8 of 10 edits hit the target with no crosshair correction.", "8 מתוך 10 עריכות פוגעות במטרה בלי תיקון כוונת."),
        T("Vary the edit shape every time so the opening moves.", "להחליף צורת עריכה כל פעם כך שהפתח זז."),
        T("Edit course or 1v1 build map with bots", "מסלול עריכות או מפת 1 על 1 עם בוטים"),
        ("EDIT_CROSSHAIR_OFF", "EDIT_WRONG_TIMING", "EDIT_NO_PRE_EDIT")),
    # ---------------- building ----------------
    ExerciseTemplate(
        "build_protected_tunnel", "building", B, "easy", 10,
        T("Protected tunneling", "טאנלינג מוגן"),
        T("Move forward with walls on every exposed side and a cone above.", "להתקדם עם קירות בכל צד חשוף וקונוס מעל."),
        T("In free build: tunnel 20 tiles forward. Each step = floor, 3 walls, cone. Then tunnel while turning left and right.",
          "בבנייה חופשית: טאנל 20 משבצות קדימה. כל צעד = רצפה, 3 קירות, קונוס. אחר כך טאנל תוך פנייה ימינה ושמאלה."),
        T("No missing piece in 20 steps (check by looking back).", "אין חלק חסר ב-20 צעדים (לבדוק במבט אחורה)."),
        T("Do it with a friend or bot shooting from the side.", "לעשות עם חבר או בוט שיורה מהצד."),
        T("Free build island", "אי בנייה חופשית"),
        ("BUILD_TUNNEL_GAP", "BUILD_UNPROTECTED_SIDE")),
    ExerciseTemplate(
        "build_retakes", "building", B, "medium", 12,
        T("Protected retakes", "ריטייקים מוגנים"),
        T("Regain height from cover with a sequence the opponent can't predict.", "להחזיר גובה מכיסוי ברצף שהיריב לא צופה."),
        T("Start under an opponent's ramp (or a bot on top). Practice 3 different retakes (side-jump, wall-cone-ramp, "
          "double ramp). Always place cover before the first ramp.",
          "התחל מתחת לרמפה של יריב (או בוט למעלה). תרגל 3 ריטייקים שונים (קפיצה לצד, קיר-קונוס-רמפה, "
          "רמפה כפולה). תמיד להניח כיסוי לפני הרמפה הראשונה."),
        T("Gain height in 7 of 10 attempts without taking a free shot.", "להשיג גובה ב-7 מתוך 10 ניסיונות בלי לספוג ירייה חינם."),
        T("Practice against a real player in a 1v1 map.", "לתרגל מול שחקן אמיתי במפת 1 על 1."),
        T("1v1 build map", "מפת 1 על 1 בבנייה"),
        ("BUILD_FAILED_RETAKE", "BUILD_LOST_HIGH_GROUND", "BUILD_LOW_GROUND_EXPOSED")),
    ExerciseTemplate(
        "build_pressure", "building", B, "medium", 10,
        T("Building under pressure", "בנייה תחת לחץ"),
        T("A structured defense instead of panic spam.", "הגנה מסודרת במקום ספאם בפאניקה."),
        T("Have a friend/bot shoot you from different angles. On every hit: wall toward the shot, floor, cone, then "
          "re-evaluate. Count pieces placed per defense.",
          "שחבר/בוט יירה עליך מזוויות שונות. בכל פגיעה: קיר לכיוון הירייה, רצפה, קונוס, ואז הערכה מחדש. "
          "לספור כמה חלקים הונחו בכל הגנה."),
        T("Each defense done with 3-5 pieces and no extra spam.", "כל הגנה מבוצעת עם 3-5 חלקים בלי ספאם מיותר."),
        T("Add a second shooter or reduce materials.", "להוסיף יורה שני או להקטין חומרים."),
        T("1v1 build map or box fight map", "מפת 1 על 1 או מפת בוקס פייט"),
        ("BUILD_PANIC_SPAM", "BUILD_LATE_PROTECTION", "BUILD_OVERBUILD")),
    ExerciseTemplate(
        "build_nineties", "building", B, "easy", 10,
        T("90s height ladder", "סולם 90s לגובה"),
        T("Win the height race with clean, fast 90s.", "לנצח במרוץ לגובה עם 90s נקיים ומהירים."),
        T("Free build: do 90s up to the height limit and back down, 5 times each direction. Then race a friend or a "
          "timer: who reaches 10 turns first. Count broken turns (a missed wall/ramp) and restart the set on each one.",
          "בנייה חופשית: 90s עד גבול הגובה ובחזרה למטה, 5 פעמים לכל כיוון. אחר כך מרוץ מול חבר או טיימר: מי מגיע "
          "ראשון ל-10 סיבובים. לספור סיבובים שבורים (קיר/רמפה שהוחמצו) ולהתחיל את הסט מחדש על כל אחד."),
        T("10 clean turns in a row with no broken piece.", "10 סיבובים נקיים ברצף בלי אף חלק שבור."),
        T("Add a friend shooting at you, or switch to side-jump 90s.", "להוסיף חבר שיורה עליך, או לעבור ל-90s עם קפיצות לצד."),
        T("Free build island", "אי בנייה חופשית"),
        ("BUILD_SLOW_HEIGHT", "BUILD_LOST_HIGH_GROUND")),
    # ---------------- piece control ----------------
    ExerciseTemplate(
        "pc_wall_take", "piece_control", P, "medium", 12,
        T("Take the wall, protect first", "לקחת את הקיר, קודם להגן"),
        T("Claim walls only after the other side is covered.", "לתפוס קירות רק אחרי שהצד השני מכוסה."),
        T("In a box fight map: before every wall take, place a wall/floor on your exposed side (usually left). "
          "Then take the opponent's wall and look for the shot.",
          "במפת בוקס פייט: לפני כל לקיחת קיר, שים קיר/רצפה בצד החשוף שלך (בדרך כלל שמאל). "
          "ואז קח את הקיר של היריב וחפש את הירייה."),
        T("10 wall takes in a row where you were not hit from the side.", "10 לקיחות קיר ברצף שבהן לא נפגעת מהצד."),
        T("Do it against a stronger player.", "לעשות מול שחקן חזק יותר."),
        T("Box fight map", "מפת בוקס פייט"),
        ("PC_ATTACK_WITHOUT_PROTECTION", "PC_LOST_WALL", "PC_NO_LOCK_AFTER_TAKE")),
    ExerciseTemplate(
        "pc_trap_convert", "piece_control", P, "hard", 15,
        T("Trap and convert", "לכלוא ולסגור"),
        T("Close escape routes, then turn control into damage.", "לסגור נתיבי בריחה, ואז להפוך שליטה לנזק."),
        T("Against a friend: when they turtle, claim their cone/floor before them, then edit for a shot within 2 seconds. "
          "Count how many controls ended in damage.",
          "מול חבר: כשהוא מסתגר, תפוס את הקונוס/רצפה שלו לפניו, ואז ערוך לירייה תוך 2 שניות. "
          "לספור כמה השתלטויות נגמרו בנזק."),
        T("At least half of your piece takes end in damage.", "לפחות חצי מההשתלטויות נגמרות בנזק."),
        T("Play first-to-5 box fights using only this approach.", "לשחק בוקס פייטס עד 5 רק בגישה הזו."),
        T("Box fight map", "מפת בוקס פייט"),
        ("PC_OPPONENT_ESCAPED", "PC_NO_FOLLOW_UP", "PC_UNSAFE_PEEK")),
    # ---------------- aim ----------------
    ExerciseTemplate(
        "aim_crosshair_height", "aim", A, "easy", 8,
        T("Crosshair height discipline", "משמעת גובה כוונת"),
        T("Crosshair always at head/chest height where enemies appear.", "כוונת תמיד בגובה ראש/חזה במקום שבו יריבים מופיעים."),
        T("In an aim map, walk around corners and ramps. Before every corner, place the crosshair where a head would be. "
          "Record yourself for 1 minute and check.",
          "במפת כיוון, הסתובב סביב פינות ורמפות. לפני כל פינה, שים את הכוונת איפה שהראש יהיה. "
          "הקלט את עצמך דקה אחת ובדוק."),
        T("In your recording the crosshair stays at the right height around corners.", "בהקלטה הכוונת נשארת בגובה הנכון סביב פינות."),
        T("Add moving targets.", "להוסיף מטרות זזות."),
        T("Aim trainer map", "מפת אימון כיוון"),
        ("AIM_CROSSHAIR_LOW", "AIM_EARLY_SHOT")),
    ExerciseTemplate(
        "aim_tracking", "aim", A, "medium", 10,
        T("Tracking moving targets", "מעקב אחרי מטרות זזות"),
        T("Keep damage on a strafing target (SMG/AR).", "לשמור נזק על מטרה שזזה לצדדים (SMG/רובה)."),
        T("Use moving bots: 5 x 1-minute tracking rounds, rest 30 s between. Focus on smooth mouse movement, not flicks.",
          "השתמש בבוטים זזים: 5 סבבים של דקה מעקב, 30 שניות מנוחה ביניהם. להתמקד בתנועת עכבר חלקה, לא בפליקים."),
        T("Visible hits keep landing for most of each round.", "פגיעות נראות ממשיכות לרוב הסבב."),
        T("Faster bots or longer rounds.", "בוטים מהירים יותר או סבבים ארוכים יותר."),
        T("Aim trainer map with moving bots", "מפת אימון כיוון עם בוטים זזים"),
        ("AIM_LOST_TRACKING", "AIM_MISSED_OPEN_SHOT")),
    ExerciseTemplate(
        "aim_flicks", "aim", A, "medium", 8,
        T("Flick and confirm", "פליק ואישור"),
        T("Accurate first shot on targets that appear suddenly.", "ירייה ראשונה מדויקת על מטרות שמופיעות פתאום."),
        T("Flick practice in an aim map with a shotgun. Only shoot when the crosshair has stopped on the target.",
          "תרגול פליקים במפת כיוון עם שוטגאן. לירות רק כשהכוונת נעצרה על המטרה."),
        T("Most first shots hit; no panic shots.", "רוב היריות הראשונות פוגעות; בלי יריות בפאניקה."),
        T("Smaller targets or more distance.", "מטרות קטנות יותר או מרחק גדול יותר."),
        T("Aim trainer map", "מפת אימון כיוון"),
        ("AIM_EARLY_SHOT", "AIM_MISSED_OPEN_SHOT", "AIM_WRONG_WEAPON_RANGE")),
    # ---------------- mechanics ----------------
    ExerciseTemplate(
        "mech_pre_fire", "mechanics", Skill.MECHANICS, "medium", 10,
        T("Pre-fire the opening", "פרי-פייר לפתח"),
        T("Your shot is already on the way when the opening appears.", "הירייה שלך כבר בדרך כשהפתח מופיע."),
        T("In an edit course or 1v1 map with a friend: aim at where the opponent/window will be, start the edit and click "
          "the shot at the same moment the edit confirms. Then practice shooting around corners the opponent must cross.",
          "במסלול עריכות או מפת 1 על 1 עם חבר: כוון למקום שבו יהיה היריב/החלון, התחל את העריכה ולחץ ירייה באותו רגע "
          "שהעריכה מאושרת. אחר כך תרגל ירי לפינות שהיריב חייב לעבור בהן."),
        T("In 10 edit-peeks, the shot lands as the edit opens at least 7 times.", "ב-10 פיקים עם עריכה, הירייה נוחתת עם פתיחת העריכה לפחות 7 פעמים."),
        T("Do it while moving, then with double edits.", "לעשות את זה בתנועה, ואז עם עריכות כפולות."),
        T("Edit course or 1v1 map", "מסלול עריכות או מפת 1 על 1"),
        ("MECH_NO_PRE_FIRE", "EDIT_WRONG_TIMING", "EDIT_CROSSHAIR_OFF")),
    ExerciseTemplate(
        "mech_swap_combo", "mechanics", Skill.MECHANICS, "medium", 8,
        T("Shotgun → SMG swap combo", "קומבו החלפה שוטגאן ← SMG"),
        T("Follow every shotgun hit with an instant swap and spray.", "להמשיך כל פגיעת שוטגאן בהחלפה מיידית וריסוס."),
        T("Aim map with moving bots: shotgun shot, swap immediately (same key every time), track with SMG/AR. "
          "Keep the swap key on a comfortable bind.",
          "מפת כיוון עם בוטים בתנועה: ירייה בשוטגאן, החלפה מיד (אותו מקש כל פעם), מעקב עם SMG/AR. "
          "שמור את מקש ההחלפה על כפתור נוח."),
        T("20 combos in a row without a pause between the shotgun shot and the spray.", "20 קומבו ברצף בלי הפסקה בין ירייה בשוטגאן לריסוס."),
        T("Add a protective wall between the two shots.", "להוסיף קיר הגנה בין שתי היריות."),
        T("Aim trainer map with moving bots", "מפת אימון כיוון עם בוטים בתנועה"),
        ("MECH_SLOW_SWAP", "FIGHT_NO_FOLLOW_UP", "MECH_MISSED_JUMP_SHOT")),
    ExerciseTemplate(
        "mech_build_edit_flow", "mechanics", Skill.MECHANICS, "hard", 12,
        T("Build-edit flow: crank, waterfall, piece swap", "רצף בנייה-עריכה: קרנק, מפל, החלפת חלקים"),
        T("Sequences that do not break under speed.", "רצפים שלא נשברים במהירות."),
        T("Free build: 2 min cranking 90s up and a protected waterfall down; 2 min ramp rush with walls; "
          "2 min wall-replace (break your own wall with a pickaxe and replace instantly); 2 min edit-place-shoot combos. Slow first, then speed up.",
          "בנייה חופשית: 2 דק' קרנקינג 90s למעלה וירידת מפל מוגנת למטה; 2 דק' ראמפ ראש עם קירות; "
          "2 דק' wall replace (שבור קיר שלך במכוש והחלף מיד); 2 דק' קומבו עריכה-בנייה-ירייה. קודם לאט, אחר כך מהר."),
        T("Each part done without a broken sequence for a full minute.", "כל חלק בוצע בלי רצף שבור במשך דקה שלמה."),
        T("Same routine against a friend who shoots at you.", "אותה שגרה מול חבר שיורה עליך."),
        T("Free build island", "אי בנייה חופשית"),
        ("MECH_BROKEN_SEQUENCE", "MECH_UNSAFE_WATERFALL", "MECH_RAMP_RUSH_NO_COVER", "MECH_SLOW_PIECE_SWAP",
         "BUILD_SLOW_HEIGHT")),
    # ---------------- movement ----------------
    ExerciseTemplate(
        "move_strafe_peek", "mechanics", M, "medium", 8,
        T("Strafe and peek", "סטרייף ופיק"),
        T("Never be a still target while exposed.", "אף פעם לא להיות מטרה עומדת כשאתה חשוף."),
        T("With a friend or bot shooting: peek out, take one shot, strafe back to cover. Change rhythm every time.",
          "עם חבר או בוט שיורה: צא לפיק, ירייה אחת, סטרייף חזרה לכיסוי. להחליף קצב כל פעם."),
        T("You take noticeably fewer hits than when standing still.", "אתה נפגע הרבה פחות מאשר כשאתה עומד במקום."),
        T("Add jumps at unpredictable moments.", "להוסיף קפיצות ברגעים לא צפויים."),
        T("1v1 map", "מפת 1 על 1"),
        ("MOVE_STATIC_IN_FIGHT", "MOVE_PREDICTABLE_STRAFE", "MOVE_BAD_JUMP", "MOVE_INEFFICIENT_PATH")),
    # ---------------- game sense ----------------
    ExerciseTemplate(
        "gs_zone_rotation", "zone_wars", G, "medium", 15,
        T("Early rotations in Zone Wars", "רוטציות מוקדמות בזון וורס"),
        T("Rotate before the zone forces you, to a position you choose.", "לבצע רוטציה לפני שהאזור מכריח אותך, למיקום שאתה בוחר."),
        T("Play Zone Wars. Every time a new zone appears, decide within 5 seconds where you will be, then move immediately. "
          "After each game, write one rotation you were late on.",
          "שחק זון וורס. בכל פעם שמופיע אזור חדש, החלט תוך 5 שניות איפה תהיה, ואז זוז מיד. "
          "אחרי כל משחק, רשום רוטציה אחת שבה איחרת."),
        T("No storm damage taken in 3 games in a row.", "בלי נזק מהסטורם ב-3 משחקים ברצף."),
        T("Play in larger lobbies or harder zone presets.", "לשחק בלובים גדולים יותר או בהגדרות אזור קשות יותר."),
        T("Zone Wars map", "מפת זון וורס"),
        ("GS_LATE_ROTATION", "GS_ENDGAME_POSITION")),
    ExerciseTemplate(
        "gs_fight_or_leave", "game_sense", G, "medium", 15,
        T("Fight or leave", "להילחם או לעזוב"),
        T("Only take fights you have an advantage in, and leave lost ones.", "להיכנס רק לקרבות עם יתרון, ולעזוב קרבות אבודים."),
        T("In Zone Wars or a real match: before every fight say out loud 'health / materials / height / third parties'. "
          "If two are bad, disengage.",
          "בזון וורס או במשחק אמיתי: לפני כל קרב תגיד בקול 'חיים / חומרים / גובה / צד שלישי'. "
          "אם שניים מהם רעים, להתנתק."),
        T("Your next analyzed video shows fewer GS_OVERPUSH / GS_NO_DISENGAGE mistakes.", "בסרטון הבא שתנתח יש פחות טעויות של דחיפת יתר ואי-התנתקות."),
        T("Make the call in under 2 seconds.", "לקבל את ההחלטה בפחות מ-2 שניות."),
        T("Zone Wars map or a real match", "מפת זון וורס או משחק אמיתי"),
        ("GS_BAD_FIGHT_SELECTION", "GS_OVERPUSH", "GS_NO_DISENGAGE", "GS_THIRD_PARTIED", "GS_LOW_RESOURCES")),
    # ---------------- realistic / box fights (fight execution) ----------------
    ExerciseTemplate(
        "realistic_protect_open", "realistic_1v1", F, "medium", 15,
        T("Realistic 1v1: protected openings", "ריאליסטיק 1 על 1: פתיחות מוגנות"),
        T("Open every fight with protection, then follow up.", "לפתוח כל קרב עם הגנה, ואז להמשיך."),
        T("Play realistic 1v1s. Rule: first action of every fight is a protective piece, second is the shot. "
          "After landing damage, push only if you are protected.",
          "שחק ריאליסטיק 1 על 1. חוק: הפעולה הראשונה בכל קרב היא חלק הגנתי, השנייה היא הירייה. "
          "אחרי שפגעת, לדחוף רק אם אתה מוגן."),
        T("Win more rounds than you lose over 10 rounds while keeping the rule.", "לנצח יותר סבבים משאתה מפסיד ב-10 סבבים תוך שמירה על החוק."),
        T("Play first-to-7 against a stronger opponent.", "לשחק עד 7 מול יריב חזק יותר."),
        T("Realistic 1v1 map", "מפת ריאליסטיק 1 על 1"),
        ("FIGHT_NO_OPENING_PROTECTION", "FIGHT_NO_FOLLOW_UP", "FIGHT_NO_RESET")),
    ExerciseTemplate(
        "boxfight_reset", "box_fights", F, "medium", 15,
        T("Box fights: reset discipline", "בוקס פייטס: משמעת איפוס"),
        T("Reset and heal instead of fighting at low health.", "להתאפס ולרפא במקום להילחם עם מעט חיים."),
        T("Box fights first-to-5. Whenever you drop below half health, fully box up and heal before the next action.",
          "בוקס פייטס עד 5. בכל פעם שאתה יורד מתחת לחצי חיים, תסגור קופסה מלאה ותרפא לפני הפעולה הבאה."),
        T("No round lost while fighting at low health without trying to reset.", "אף סבב לא הפסדת כשנלחמת עם מעט חיים בלי לנסות להתאפס."),
        T("Shorter reset time; fight a stronger opponent.", "זמן איפוס קצר יותר; מול יריב חזק יותר."),
        T("Box fight map", "מפת בוקס פייט"),
        ("FIGHT_NO_RESET", "BUILD_LATE_PROTECTION", "GS_OVERPUSH")),
)

BY_ID: dict[str, ExerciseTemplate] = {t.id: t for t in CATALOG}
WARMUP_ID = "warmup_mechanics"


def templates_for_mistake(code: str) -> list[ExerciseTemplate]:
    return [t for t in CATALOG if code in t.targets]


def templates_for_skill(skill: str) -> list[ExerciseTemplate]:
    return [t for t in CATALOG if t.skill.value == skill and t.id != WARMUP_ID]
