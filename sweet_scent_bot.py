"""
sweet_scent_bot.py -- uses Sweet Scent (Pokemon Crystal) to force wild
encounters wherever they can happen, checks each wild Pokemon, flees anything that
isn't shiny, and stops + alerts you the moment it finds one. The character
never takes a step.

Shininess comes from the shiny animation: a shiny wild Pokemon makes the
whole battle screen flash to a photo-negative for an instant before its
HP box appears; a normal one doesn't (see shiny_flash.py). No Pokemon
graphics are used. Battle Scene can be ON or OFF.
It also listens to NTR-VC's game audio for the shiny animation's sound
(shine_sound.py), read from NTR-VC's shared memory when the viewer shares
it; either check finding a shiny stops the bot.
Whenever it stops it can also ping your phone on Discord (alarm.py).

Start NTR-VC (the frame-sharing NTRViewer-HR) and run calibrate.py first. Then:
    py sweet_scent_bot.py --ip <3DS IP>

Safety rules:
  * The confirming A in battle is only pressed after the cursor is
    visually confirmed on RUN (ref_cursor_run.png), so it can never
    select FIGHT and use a move.
  * The same rule covers the field menus (see sweet_scent.py).
  * Party slot 1 must be faster than the fastest wild Pokemon where
    Sweet Scent is used. In Gen II a faster Pokemon ALWAYS escapes.
  * It only reads the game picture from NTR-VC and sends button presses --
    it never touches your ROM or save file.
"""

import argparse
import json
import os
import sys
import time
import faulthandler

from luma_input import Luma3DSInput, Button
import cv2

from vision import match_score, wait_until_stable
import gb_screen
from frame_recorder import RecordingCapture
import shared_frame
from sweet_scent import trigger_encounter, REQUIRED as MENU_CHECKS
import watch
from watch import watch as watch_for
import ntr_status
import session_log
import shine_sound
import audio_recorder
import shared_audio
import alarm

CONFIG_PATH = "config.json"

BATTLE_MATCH_THRESHOLD = 0.35  # the overworld has scored -0.07 to 0.27
                               # across real runs; stuck battle screens
                               # have scored 0.46 and 0.57. 0.35 sits in
                               # the middle of that gap with margin on
                               # both sides. Watch the printed
                               # (battle-indicator match: X.XX) lines and
                               # nudge this up/down if it ever misfires.
CURSOR_MATCH_THRESHOLD = 0.8  # how tightly the cursor-at-RUN crop must
                               # match before the confirming A is sent
MAX_NAV_NUDGES = 12            # how many times to retry navigating toward
                               # RUN before giving up SAFELY (never having
                               # risked an unverified confirm press)

NAME_TO_BUTTON = {
    "UP": Button.UP, "DOWN": Button.DOWN,
    "LEFT": Button.LEFT, "RIGHT": Button.RIGHT,
    "A": Button.A, "B": Button.B,
}


def load_config():
    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
    except FileNotFoundError:
        print(f"{CONFIG_PATH} not found -- run calibrate.py first.")
        sys.exit(1)
    if cfg.get("frame_source") != "shared" or "capture_region" in cfg:
        print("config.json is from an older setup (screen capture), which is "
              "no longer used -- run: py calibrate.py")
        sys.exit(1)
    for key in ("battle_indicator_roi", "cursor_run_roi"):
        if key not in cfg:
            print(f"config.json is missing '{key}' -- run calibrate.py "
                  f"(or, if you only need this one, "
                  f"py calibrate.py --cursor) first.")
            sys.exit(1)
    if not os.path.exists("ref_battle.png"):
        print("ref_battle.png not found -- run calibrate.py first.")
        sys.exit(1)
    if not os.path.exists("ref_cursor_run.png"):
        print("ref_cursor_run.png not found -- run "
              "py calibrate.py --cursor first.")
        sys.exit(1)
    for key, ref, _label in MENU_CHECKS + [("menu_pokemon_roi", "ref_menu_pokemon_off.png", "")]:
        if key not in cfg or not os.path.exists(ref):
            print(f"Sweet Scent menu calibration is missing ({key} / {ref}) "
                  f"-- run: py calibrate.py --menus")
            sys.exit(1)
    return cfg


def make_capture(cfg):
    """The bot's picture: NTR-VC's shared frames (so NTR-VC can be
    minimised, covered or moved while the bot runs)."""
    cap = shared_frame.SharedFrameCapture(rotation=cfg.get("shared_rotation", 1))
    print("Reading frames from NTR-VC (it can be minimised)...")
    if not shared_frame.wait_until_available(cap, timeout=15.0):
        print("No frames from NTR-VC. Start NTR-VC (the frame-sharing "
              "NTRViewer-HR), connect it to the 3DS, and run the bot again. "
              "(py test_shared_frame.py checks the connection.)")
        sys.exit(1)
    ntr_status.shared_source = cap
    return cap


def wait_until_fully_shown(cap, timeout=8.0):
    """Waits until the wild Pokemon is fully displayed: the battle text box
    has text in it ("Wild X appeared!" only prints once the sprite has
    finished sliding in, and after the shiny animation), and the text has
    finished printing (the screen is still). By then every frame the shiny
    flash could be in has been recorded. Returns the current frame."""
    end = time.time() + timeout
    while time.time() < end:
        _heartbeat()
        frame = cap.frame()
        if gb_screen.battle_text_shown(gb_screen.native(frame)):
            still = watch.wait_still(cap, 0.5, 3.0, heartbeat=_heartbeat)
            return still if still is not None else cap.frame()
        time.sleep(0.05)
    print("(text box never filled -- checking anyway)", end=" ", flush=True)
    return cap.frame()


SHINE_SHINY = 0.11     # shine-sound match at or above this: shiny. Measured
                       # on the real 3DS over NTR-VC shared audio: 35 forced
                       # shinies scored 0.12-0.23 (the emulator's 0.36 was
                       # far too optimistic), ~50,000 normal encounters never
                       # above 0.09. Over the PC-speaker path (--loopback)
                       # normals reached 0.13, so that path can false-alarm.
SHINE_NORMAL = 0.10    # below this (with live audio): normal, even when the
                       # picture had gaps
AUDIO_MIN_RMS = 0.002  # quieter than this, the audio is treated as missing


def sound_check(audio, since):
    """The shine-sound verdict for the audio recorded since `since`:
    ("shiny" | "normal" | "unsure" | None, reason). None when there's no
    usable audio (then the picture decides alone)."""
    if audio is None:
        return None, "sound check off"
    if since is None:
        return None, "no sound recorded for this battle's start"
    if audio.error is not None:
        return None, f"no audio ({audio.error})"
    x = audio.since(since)
    if len(x) < audio.sr * 2 or float(x.std()) < AUDIO_MIN_RMS:
        if isinstance(audio, shared_audio.SharedAudioRecorder):
            return None, ("no game audio heard (is NTR-VC's audio on in "
                          "its Debug window: Audio (NTR-HR+)?)")
        return None, ("no game audio heard (is NTR-VC's audio on, its "
                      "volume above 0, and --audio-device right?)")
    score, _at = shine_sound.best_match(x, audio.sr)
    if score >= SHINE_SHINY:
        return "shiny", f"shiny sound (match {score:.2f})"
    if score < SHINE_NORMAL:
        return "normal", f"no shiny sound (match {score:.2f})"
    return "unsure", f"maybe the shiny sound (match {score:.2f})"


def combine(flash, sound, sound_reason):
    """One verdict from the flash check and the sound check. Either one
    seeing a shiny is enough; a clear "no shiny sound" settles a picture
    that had gaps."""
    if flash["verdict"] == "shiny" or sound == "shiny":
        return {"verdict": "shiny",
                "reason": f"{flash['reason']}; {sound_reason}"}
    if sound == "normal":
        return {"verdict": "normal",
                "reason": f"{sound_reason}; picture: {flash['reason']}"}
    if sound == "unsure":
        return {"verdict": "unsure", "reason": sound_reason}
    return {"verdict": flash["verdict"],
            "reason": f"{flash['reason']} ({sound_reason})"}


def open_audio(args):
    """NTR-VC's shared audio when the viewer shares it (volume and output
    device don't matter), else the PC's speakers, else None."""
    if not args.loopback and shared_audio.available(timeout=2.0):
        audio = shared_audio.SharedAudioRecorder()
        print(f"Listening for the shiny sound on: {audio.device}")
        return audio
    if not args.loopback:
        print("This NTR-VC doesn't share its audio (2.2.0 or later does); "
              "listening to the PC's speakers instead.")
    try:
        audio = audio_recorder.AudioRecorder(args.audio_device)
        print(f"Listening for the shiny sound on: {audio.device}")
        return audio
    except Exception as e:
        print(f"Can't record the PC's sound ({e}); using the shiny "
              f"flash alone.")
        return None


def save_encounter_picture(frame, kind):
    """Keeps a screenshot of anything the bot stops for."""
    os.makedirs("alerts", exist_ok=True)
    path = os.path.join("alerts", time.strftime(f"%Y%m%d_%H%M%S_{kind}.png"))
    cv2.imwrite(path, frame)
    return path


_last_status_print = 0.0


HANG_REPORT_AFTER = 180   # seconds with no progress before writing a report
_hang_log = open("hang_report.txt", "a")


def _disable_console_select_freeze():
    """Windows consoles have a 'QuickEdit' mode: clicking in the window
    starts a text selection, and the program FREEZES on its next print
    until Enter/Esc is pressed. That caused a real mid-run freeze (last
    line 'sending DOWN', resumed when Enter was pressed). This switches
    QuickEdit off for this window only, while the bot runs. Harmless
    no-op on terminals that don't have it, and on non-Windows systems."""
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-10)          # console input
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            ENABLE_QUICK_EDIT_MODE, ENABLE_EXTENDED_FLAGS = 0x0040, 0x0080
            kernel32.SetConsoleMode(
                handle, (mode.value | ENABLE_EXTENDED_FLAGS) & ~ENABLE_QUICK_EDIT_MODE)
            print("(Console click-to-select disabled so a stray click "
                  "can't freeze the bot.)")
    except Exception:
        pass  # never let this stop the bot from running


def _heartbeat():
    """Re-arms the watchdog. faulthandler runs on its own C-level thread,
    so it still works if the bot freezes inside a screen grab or a
    blocked terminal write. If no heartbeat arrives within
    HANG_REPORT_AFTER seconds, it writes the exact line the bot is stuck
    on to hang_report.txt (repeating every HANG_REPORT_AFTER while
    stuck)."""
    faulthandler.dump_traceback_later(HANG_REPORT_AFTER, repeat=True,
                                      file=_hang_log)


def _wait_for_enter(prompt):
    """A deliberate pause is not a hang, so disarm the watchdog while
    waiting for you, and re-arm it afterwards."""
    faulthandler.cancel_dump_traceback_later()
    try:
        return input(prompt)
    finally:
        _heartbeat()


def in_battle(cap, cfg: dict) -> bool:
    """Also prints the raw match score every couple of seconds (even while
    on the overworld) so a silent hang is visible/debuggable instead of a
    total black box -- if the score never gets anywhere near
    BATTLE_MATCH_THRESHOLD even during a real battle, that's a
    miscalibrated battle_indicator_roi, not a stuck script."""
    global _last_status_print
    _heartbeat()
    frame = cap.frame()
    score = match_score(frame, cfg["battle_indicator_roi"], "ref_battle.png")
    result = score >= BATTLE_MATCH_THRESHOLD
    now = time.time()
    if now - _last_status_print > 2.0:
        flag = " [BATTLE]" if result else ""
        print(f"  (battle-indicator match: {score:.2f}{flag})", flush=True)
        _last_status_print = now
    return result


def _cursor_on_run(cap, cfg: dict, label: str = "") -> bool:
    _heartbeat()
    score = match_score(cap.frame(), cfg["cursor_run_roi"], "ref_cursor_run.png")
    result = score >= CURSOR_MATCH_THRESHOLD
    flag = " [RUN]" if result else ""
    print(f"    cursor check{(' after ' + label) if label else ''}: "
          f"{score:.2f}{flag}", flush=True)
    return result


MENU_VISIBLE = 0.6    # cursor_run crop: RUN text showing, arrow elsewhere
                      # scores ~0.77; text boxes score ~0.0
TEXT_A_WINDOW = 2.0   # see flee_fast() step 1
TEXT_A_SPACING = 0.7  # between those A presses
MIN_TEXT_WAIT = 1.2   # never start clearing "Wild X appeared!" sooner
                      # than this after the battle is detected


def _run_score(frame, cfg):
    return match_score(frame, cfg["cursor_run_roi"], "ref_cursor_run.png")


def _menu_on_screen(cap, cfg):
    return _run_score(cap.frame(), cfg) >= MENU_VISIBLE


def _navigate_to_run(pad: Luma3DSInput, cap, cfg: dict) -> bool:
    """Nudges toward RUN, re-checking the cursor's ACTUAL position after
    every single button instead of assuming a fixed sequence worked.
    Never sends the confirming A itself -- that only happens in flee(),
    and only once this returns True.

    A is sent AT MOST ONCE, right at the start (needed to clear the
    original "Wild X appeared!" text -- confirmed B alone doesn't do
    that in this generation). After that, navigation uses ONLY B (safe:
    backs out of any submenu, or does nothing on the main menu) and
    Down/Right (safe: these only move the main-menu cursor, they can
    never confirm or select anything). Repeating A on later nudges was
    an earlier bug: if Down/Right hadn't yet moved the cursor off FIGHT
    (e.g. a dropped packet), a repeated A would confirm FIGHT and open
    it instead of just retrying navigation -- observed as the bot
    cycling in and out of the FIGHT menu. Never doing that again is what
    makes this loop provably safe regardless of how many retries
    navigation needs."""
    if _cursor_on_run(cap, cfg, "start"):
        return True

    # Clear any lingering text, once.
    print("  -> sending B (clear text)", flush=True)
    pad.tap(Button.B, hold=0.15, gap=0.2)
    wait_until_stable(cap, samples=2, interval=0.2, max_wait=1.5)
    if _cursor_on_run(cap, cfg, "B"):
        return True
    print("  -> sending A (clear text)", flush=True)
    pad.tap(Button.A, hold=0.15, gap=0.2)
    wait_until_stable(cap, samples=2, interval=0.2, max_wait=1.5)
    if _cursor_on_run(cap, cfg, "A"):
        return True

    # Navigate using only safe buttons from here on -- no more A.
    for round_num in range(1, MAX_NAV_NUDGES + 1):
        print(f"  round {round_num}/{MAX_NAV_NUDGES}:", flush=True)
        print("    -> sending B", flush=True)
        pad.tap(Button.B, hold=0.15, gap=0.2)  # backs out of any submenu
        wait_until_stable(cap, samples=2, interval=0.2, max_wait=1.5)  # we may have landed in
        if _cursor_on_run(cap, cfg, "B"):
            return True
        # DOWN/RIGHT only while the battle MENU is on screen (twice). If
        # the battle has actually ended and a stale frame fooled us, these
        # would be real steps on the overworld -- found in simulation.
        if not (_menu_on_screen(cap, cfg) and _menu_on_screen(cap, cfg)):
            print("    (battle menu not on screen -- only B this round)", flush=True)
            time.sleep(0.6)
            continue
        print("    -> sending DOWN", flush=True)
        pad.tap(Button.DOWN, hold=0.15, gap=0.2)
        wait_until_stable(cap, samples=2, interval=0.2, max_wait=1.5)
        if _cursor_on_run(cap, cfg, "DOWN"):
            return True
        print("    -> sending RIGHT", flush=True)
        pad.tap(Button.RIGHT, hold=0.15, gap=0.2)
        wait_until_stable(cap, samples=2, interval=0.2, max_wait=1.5)
        if _cursor_on_run(cap, cfg, "RIGHT"):
            return True
    return False


MAX_CLEAR_ATTEMPTS = 5


def flee(pad: Luma3DSInput, cap, cfg: dict) -> bool:
    """Only ever presses the confirming A once the cursor's position at
    RUN has been visually verified -- this is what actually prevents
    ever accidentally selecting FIGHT and using a move, no matter which
    screen a button happens to land on. Returns False if RUN was never
    confirmed (safe -- no confirming A was sent at all) or if the battle
    somehow didn't clear after confirming it."""
    if not _navigate_to_run(pad, cap, cfg):
        print("  Couldn't visually confirm the cursor reached RUN after "
              "several tries -- NOT pressing A (avoiding any risk of "
              "selecting a move).", flush=True)
        return False

    print("  Cursor confirmed at RUN -- confirming.", flush=True)
    pad.tap(Button.A, hold=0.15, gap=0.2)
    wait_until_stable(cap, samples=2, interval=0.2, max_wait=2.5)

    # Clear "Got away safely!" -- generous retries are safe here (not
    # stingy like the RUN-confirm step has to be), since escaping a wild
    # battle in this generation always succeeds once RUN is confirmed,
    # so every press from here on can only ever clear lingering text,
    # never risk selecting a move.
    for attempt in range(1, MAX_CLEAR_ATTEMPTS + 1):
        pad.tap(Button.A, hold=0.15, gap=0.2)
        wait_until_stable(cap, max_wait=5.0)
        if not in_battle(cap, cfg):
            return True
        print(f"  Still looks like a battle -- clearing attempt "
              f"{attempt}/{MAX_CLEAR_ATTEMPTS}.", flush=True)
    return False


def _battle_frame(frame, cfg):
    return match_score(frame, cfg["battle_indicator_roi"], "ref_battle.png") >= BATTLE_MATCH_THRESHOLD


def flee_fast(pad, cap, cfg) -> bool:
    """The same guarantees as flee(), but reacting to the stream as it
    updates instead of waiting on timers. Falls back to flee() whenever
    anything is unclear.

    1. "Wild X appeared!" needs A. After it's cleared, the game ALWAYS
       takes ~4.2 s ("Go! <POKEMON>!" + send-out) before the menu can
       appear (measured: 72.75 s -> 76.93 s in the recording). So a
       missed A may be retried, but only within TEXT_A_WINDOW (2 s) of
       the first one -- none of them can ever land on the menu.
    2. Wait until the menu is actually visible (no blind presses into
       text boxes).
    3. DOWN + RIGHT reaches RUN from any menu position. The confirming A
       is only pressed once RUN is seen on two looks after those presses.
    4. After that, A until the overworld is back -- safe, because with a
       faster lead escaping always succeeds, so A can only clear text."""
    hb = _heartbeat
    run_visible = lambda f: _run_score(f, cfg) >= MENU_VISIBLE
    run_selected = lambda f: _run_score(f, cfg) >= CURSOR_MATCH_THRESHOLD
    print("  Fleeing (fast):", flush=True)

    # 1. Clear "Wild X appeared!" -- unless the menu is somehow already up.
    #    Three A presses spread over ~1.5 s, all inside TEXT_A_WINDOW: if
    #    one lands too early (intro still playing) or gets lost, the next
    #    one clears it. None can reach the menu, which needs ~4.2 s after
    #    the text clears -- and nothing but our own A can clear it.
    menu_already_up, _ = watch.holds(cap, run_visible, heartbeat=hb)
    if not menu_already_up:
        first = time.time()
        for n in range(1, 4):
            if time.time() - first > TEXT_A_WINDOW - watch.HOLD:
                break
            watch.tap(pad, Button.A, f"A (clear 'Wild ... appeared!') {n}/3")
            time.sleep(TEXT_A_SPACING)

    # 2. Wait for the battle menu.
    frame = watch_for(cap, run_visible, 6.5, heartbeat=hb)
    if frame is None:
        print("  Battle menu never showed -- using the slow flee.", flush=True)
        return flee(pad, cap, cfg)

    # 3. Onto RUN.
    for _ in range(6):
        confirmed, frame = watch.holds(cap, run_selected, heartbeat=hb)
        if confirmed:
            break
        watch.tap(pad, Button.DOWN, "DOWN")
        watch.tap(pad, Button.RIGHT, "RIGHT")
        got = watch_for(cap, run_selected, watch.RETRY_AFTER, before=frame, heartbeat=hb)
        frame = got if got is not None else cap.frame()
        if got is not None:
            break
    else:
        print("  Couldn't confirm RUN quickly -- using the slow flee.", flush=True)
        return flee(pad, cap, cfg)
    print("  Cursor confirmed at RUN -- confirming.", flush=True)
    watch.tap(pad, Button.A, "A (verified: RUN)")

    # 4. Clear "Got away safely!" and wait for the overworld.
    end = time.time() + 8.0
    presses = 0
    while time.time() < end:
        if watch_for(cap, lambda f: not _battle_frame(f, cfg), 0.8, heartbeat=hb) is not None:
            # (the next Sweet Scent waits for the overworld to settle)
            print(f"  Battle over ({presses} A presses to clear the text).", flush=True)
            return True
        if ntr_status.is_down():
            time.sleep(0.25)    # a dip: hold off, keep watching
            continue
        watch.tap(pad, Button.A, "A", log=False)
        presses += 1
    return False


RECOVERY_WAITS = [10, 20, 30, 60, 60, 60, 60, 60]  # ~6 minutes in total


def recover_from_stuck_battle(pad, cap, cfg) -> bool:
    """Called when flee() couldn't confirm getting back to the overworld.
    Most likely cause (seen at encounter #847 in a real 10-hour log): a
    short Wi-Fi hiccup where button presses stop reaching the 3DS for a
    while. Rather than pausing on the first failure -- which once turned
    a brief outage into a 4-hour stop -- wait and retry the whole
    verified flee a few times. Safe to repeat: flee() never presses the
    confirming A unless the cursor is visually confirmed on RUN."""
    for i, wait in enumerate(RECOVERY_WAITS, start=1):
        print(f"  Recovery {i}/{len(RECOVERY_WAITS)}: waiting {wait}s, "
              f"then retrying the flee.", flush=True)
        pad.release_all()
        pad.send()
        time.sleep(wait)
        if not in_battle(cap, cfg):
            print("  Back on the overworld -- recovered.", flush=True)
            return True
        if flee(pad, cap, cfg):
            print("  Flee worked this time -- recovered.", flush=True)
            return True
    return False


MAX_TRIGGER_FAILURES = 3      # pause for you after this many Sweet Scent
                               # attempts in a row go wrong


# What the Discord alert reports; main() fills these in.
_run = {"cfg": {}, "start": time.time(), "encounters": 0}


def pause_for_user(pad, message, kind="paused", detail="", picture=None):
    """Stops pressing buttons until ENTER. Also sends the Discord alert
    (alarm.py; kind "shiny", "unsure" or "paused", `detail` says why)
    if a webhook is set up -- in the background, so the pause starts at once."""
    print(f"\n*** [{time.strftime('%H:%M:%S')}] {message} ***")
    alert = alarm.notify(_run["cfg"], alarm.format_alert(
        kind, _run["encounters"], time.time() - _run["start"], detail), picture)
    print("The bot is NOT sending any buttons now; it's waiting for you to "
          "press ENTER in this window.")
    pad.release_all()
    pad.send()
    pad.return_control()
    _wait_for_enter("Press ENTER to resume (Ctrl+C instead to quit): ")
    alert(0.5)


def ntr_dead_what():
    reason = ntr_status.last_reason or "0%"
    return {"not responding": "NTR-VC / NTR Viewer has stopped responding "
                              "(Windows reports it as Not Responding)",
            "closed": "NTR-VC / NTR Viewer has been closed",
            "frozen": "NTR-VC has stopped updating (its heartbeat stalled)",
            "0%": "NTR Viewer has shown Connection Quality 0.0% -- the 3DS "
                  "has probably frozen or disconnected"}[reason]


def ntr_dead_message():
    return (f"{ntr_dead_what()}, for 30 seconds straight. The bot pressed "
            f"nothing while the picture couldn't be trusted. PAUSED. Get NTR-VC and the 3DS "
            f"running and streaming again, go to the overworld with no menu "
            f"open, then press ENTER.")


STREAM_BACK_FOR = 5.0   # seconds the stream must stay up before resuming
STREAM_NAG_AFTER = 20 * 60  # still down after this long: alert "needs you"
                            # (once), and keep waiting
CLEAR_MENU_PRESSES = 4  # B presses after a drop: back out of any menu the
                        # bot was in (B does nothing on the overworld)


def wait_out_stream_drop(pad):
    """Connection Quality 0% with NTR-VC itself fine means the 3DS stopped
    streaming. NTR-VC keeps reconnecting on its own (a real drop came back
    after 11 minutes), so instead of stopping until ENTER, wait for the
    picture to return and carry on. Presses nothing while waiting; Ctrl+C
    still quits."""
    dropped_at = time.time()
    print(f"\n*** [{time.strftime('%H:%M:%S')}] {ntr_dead_what()}, for 30 "
          f"seconds straight. NTR-VC keeps reconnecting by itself; the bot "
          f"presses nothing until the picture is back, then carries on. ***",
          flush=True)
    alarm.notify(_run["cfg"], alarm.format_alert(
        "stream", _run["encounters"], time.time() - _run["start"],
        "The 3DS stopped streaming to NTR-VC (Connection Quality 0%). "
        "NTR-VC is reconnecting; the bot resumes on its own when the "
        "picture is back."))
    pad.release_all()
    pad.send()
    pad.return_control()
    faulthandler.cancel_dump_traceback_later()   # a long wait isn't a hang
    try:
        up_since, nagged = None, False
        while True:
            time.sleep(0.5)
            if not nagged and time.time() - dropped_at >= STREAM_NAG_AFTER:
                nagged = True
                print(f"  Still no picture after {STREAM_NAG_AFTER // 60} min "
                      f"-- check the 3DS. Still waiting; it carries on by "
                      f"itself once the picture is back.", flush=True)
                alarm.notify(_run["cfg"], alarm.format_alert(
                    "paused", _run["encounters"], time.time() - _run["start"],
                    f"The 3DS has sent no picture for {STREAM_NAG_AFTER // 60} "
                    f"minutes. Check that it's on and NTR is streaming; the "
                    f"bot carries on by itself once the picture is back."))
            if ntr_status.down_reason() is None:
                up_since = up_since or time.time()
                if time.time() - up_since >= STREAM_BACK_FOR:
                    break
            else:
                up_since = None
    finally:
        _heartbeat()
    print(f"  Picture back after {(time.time() - dropped_at) / 60:.1f} min "
          f"-- backing out of any menu and carrying on.", flush=True)
    for _ in range(CLEAR_MENU_PRESSES):
        pad.tap(Button.B, hold=0.15, gap=0.4)


def wait_for_live_stream(pad):
    """If NTR Viewer reports a dead stream, wait it out: on its own for a
    3DS that stopped streaming, or paused until ENTER if NTR-VC itself
    closed or froze. Returns True if it had to wait."""
    paused = False
    while ntr_status.stream_dead(heartbeat=_heartbeat):
        if ntr_status.last_reason == "0%":
            wait_out_stream_drop(pad)
        else:
            pause_for_user(pad, ntr_dead_message(),
                           detail=ntr_dead_what() + ", for 30 seconds straight.")
        paused = True
    return paused


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", required=True,
                         help="3DS IP address, shown in Rosalina's "
                              "InputRedirection screen")
    parser.add_argument("--no-sound", action="store_true",
                         help="don't listen for the shiny sound; use the "
                              "shiny flash alone")
    parser.add_argument("--audio-device",
                         help="only with an NTR-VC older than 2.2.0 (no "
                              "audio sharing): listen to this output device "
                              "(part of its name) instead of the default "
                              "speakers, e.g. \"Steam Streaming\" (see "
                              "audio_recorder.py)")
    parser.add_argument("--loopback", action="store_true",
                         help="listen to the PC's speakers even if NTR-VC "
                              "shares its audio")
    args = parser.parse_args()
    log_path = session_log.start()
    _disable_console_select_freeze()
    print(f"Logging this session to {log_path}")

    cfg = load_config()
    _run["cfg"] = cfg
    if cfg.get("discord_webhook_url"):
        print("Discord alert: on (py alarm.py --test sends a test).")
    else:
        print("Discord alert: off (py alarm.py --setup turns it on).")
    cap = RecordingCapture(make_capture(cfg))
    pad = Luma3DSInput(args.ip)
    audio = None
    if not args.no_sound:
        audio = open_audio(args)
    watch.install(pad)       # presses from every code path take turns
    print("Shiny check: watching for the shiny flash.")
    print("Start on the overworld, on a tile where wild Pokemon appear "
          "(grass, water while surfing, or a cave/dungeon floor), with no "
          "menu open. Party slot 1 must know Sweet Scent AND be faster than "
          "the fastest wild Pokemon there.")

    encounters = 0
    attempt_start = None   # set when an attempt starts recording; a battle
                           # already on screen at startup has no recording
                           # of its intro, so the sound can't vouch for it
    trigger_failures = 0
    start = time.time()
    _run["start"] = start
    last_flee_ok = False   # fast menus only from a known state

    try:
        _hang_log.write(f"\n=== session started {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        _hang_log.flush()
        _heartbeat()
        while True:
            if wait_for_live_stream(pad):
                last_flee_ok, trigger_failures = False, 0
            fast = last_flee_ok
            last_flee_ok = False
            # Already in a battle (e.g. a Sweet Scent attempt gave up just as
            # the encounter began)? Handle it first -- pressing START in a
            # battle does nothing, so the bot would otherwise loop forever.
            already_in_battle = _battle_frame(cap.frame(), cfg) and watch.holds(
                cap, lambda f: _battle_frame(f, cfg), 0.5, heartbeat=_heartbeat)[0]
            if already_in_battle:
                # The recording is NOT cleared here: if this battle started
                # during the last attempt, its intro (and any flash) is
                # still in it. If not, the check comes out "can't tell".
                print("  Already in a battle -- handling it before anything else.", flush=True)
            else:
                cap.clear()      # this attempt's frames only
                attempt_start = time.time()
            if not already_in_battle and not trigger_encounter(
                    pad, cap, cfg, in_battle, _heartbeat, fast=fast):
                if wait_for_live_stream(pad):     # the real reason it failed
                    trigger_failures = 0
                    continue
                trigger_failures += 1
                if trigger_failures >= MAX_TRIGGER_FAILURES:
                    pause_for_user(pad, f"Sweet Scent didn't work "
                                   f"{trigger_failures} times in a row -- "
                                   f"PAUSED. Get back to the overworld with no "
                                   f"menu open, cursor on slot 1 in the party.",
                                   detail=f"Sweet Scent didn't work "
                                          f"{trigger_failures} times in a row.")
                    trigger_failures = 0
                continue
            trigger_failures = 0

            # Until the wild Pokemon has slid in and "Wild X appeared!" has
            # finished printing (the screen stops changing).
            battle_seen_at = time.time()
            ntr_status.wait_for_good_quality(heartbeat=_heartbeat)
            # Wait until the wild Pokemon is FULLY displayed ("Wild X
            # appeared!" is in the text box) -- a still screen alone isn't
            # enough: a stalled stream once froze mid-intro.
            frame = wait_until_fully_shown(cap)
            # The text is never ready sooner than ~2.2 s after the battle
            # appears; a slow stream can repeat a frame and fake "still".
            while time.time() - battle_seen_at < MIN_TEXT_WAIT:
                time.sleep(0.05)
                frame = cap.frame()
            encounters += 1
            _run["encounters"] = encounters
            elapsed_min = (time.time() - start) / 60
            print(f"[{elapsed_min:.1f} min] Encounter #{encounters}...", end=" ")

            sound, sound_reason = sound_check(audio, attempt_start)
            result = combine(cap.analyse(), sound, sound_reason)
            kind = result["verdict"]
            if kind == "normal":
                print(f"normal ({result['reason']}). Fleeing.")
            else:
                picture = save_encounter_picture(frame, kind)
                if kind == "shiny":
                    print(f"SHINY! ({result['reason']})")
                    message = (f"SHINY! The shiny flash played ({result['reason']}). "
                               f"Take over now! Screenshot: {picture}. Resume "
                               f"from the overworld with no menu open.")
                else:
                    print(f"can't tell: {result['reason']}.")
                    message = (f"COULDN'T TELL whether this one is shiny: "
                               f"{result['reason']}. Check it yourself. Screenshot: "
                               f"{picture}. If it's normal, run from it, then "
                               f"resume from the overworld with no menu open.")
                pause_for_user(pad, message, kind, result["reason"], picture)
                continue

            # A battle we walked into mid-way gets the original fully checked
            # flee: the fast one's quick A presses are only safe while
            # "Wild X appeared!" is known to still be waiting.
            if (flee(pad, cap, cfg) if already_in_battle else flee_fast(pad, cap, cfg)):
                last_flee_ok = True
            elif wait_for_live_stream(pad):
                pass    # resumed after the user fixed the 3DS; start fresh
            elif not recover_from_stuck_battle(pad, cap, cfg):
                pause_for_user(pad, "Still stuck in a battle after ~6 minutes "
                               "of retries -- PAUSED.",
                               detail="Still stuck in a battle after ~6 "
                                      "minutes of retries.")

    except KeyboardInterrupt:
        elapsed_min = (time.time() - start) / 60
        print(f"\nStopped after {encounters} encounters in {elapsed_min:.1f} min.")
    finally:
        cap.close()
        pad.close()
        if audio is not None:
            audio.close()


if __name__ == "__main__":
    main()
