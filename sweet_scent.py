"""
sweet_scent.py -- forces a wild encounter with Sweet Scent from the field
menu: START -> POKeMON -> first Pokemon -> SWEET SCENT.

Safety rules (each one earned in testing):
  * A is only pressed on START-menu items after a screenshot confirms the
    cursor is on POKeMON. Gen II menus can remember where the cursor was
    left, so a fixed button sequence isn't safe.
  * START toggles the menu. Pressing it while the menu is already open
    (hidden by a stale stream frame) would close it, and then direction
    presses would walk the character. So the bot always presses B first
    (closes any menu, does nothing on the overworld), waits out the
    stream lag, and only then presses START.
  * Direction presses are only sent after the START menu is confirmed
    open, so they can only move a menu cursor, never the player.
  * The party screen: A on whatever is under the cursor (slot 1), with
    no checks and no cursor movement, by design.
  * SWEET SCENT is looked at (never navigated to) before its A. If it's
    not there, something unexpected is open, so back out with B.
  * Recovery only ever uses B, which backs out of every field menu and
    does nothing on the overworld or on battle text.
"""

import os
import shutil
import time

import cv2

from luma_input import Button
from vision import match_score
import watch
from watch import watch as watch_for
import ntr_status

DEBUG_DIR = "debug_sweet_scent"
DEBUG_KEEP = 10            # keep the last 10 attempts' pictures
_debug_step = 0
_debug_attempt_dir = DEBUG_DIR

MENU_MATCH_THRESHOLD = 0.75
MENU_SETTLE = 1.5          # NTR Viewer can drop to 1-3 FPS, so give each
                            # press time to actually show up on the stream
CONFIRM_GAP = 0.8          # second look, to rule out a stale frame
CLOSED_WAIT = 2.0          # after B, wait this long before pressing START
A_HOLD = 0.15              # same hold as the battle A presses, which have
                            # been reliable across thousands of flees
MAX_A_TRIES = 3            # re-press A if the screen didn't change
SWEET_SCENT_TIMEOUT = 15.0 # how long to wait for the encounter to start

# (config key, reference image, label)
START_MENU_OPEN = ("start_menu_roi", "ref_start_menu.png", "start menu open")
CURSOR_POKEMON = ("menu_pokemon_roi", "ref_menu_pokemon.png", "cursor on POKEMON")
POKEMON_OFF_REF = "ref_menu_pokemon_off.png"   # same box, cursor on POKEDEX
CURSOR_MARGIN = 0.05       # arrow-present must beat arrow-absent by this
CURSOR_SWEET = ("sweet_scent_roi", "ref_sweet_scent.png", "cursor on SWEET SCENT")

REQUIRED = [START_MENU_OPEN, CURSOR_POKEMON, CURSOR_SWEET]


def _looks(cap, cfg, target, heartbeat):
    """True only if two separate frames, a moment apart, both match -- so
    a stale stream frame can never green-light an A press."""
    heartbeat()
    key, ref, label = target
    time.sleep(MENU_SETTLE)
    s1 = match_score(cap.frame(), cfg[key], ref)
    s2 = None
    if s1 >= MENU_MATCH_THRESHOLD:
        time.sleep(CONFIRM_GAP)
        s2 = match_score(cap.frame(), cfg[key], ref)
    ok = s2 is not None and s2 >= MENU_MATCH_THRESHOLD
    shown = f"{s1:.2f}" + (f"/{s2:.2f}" if s2 is not None else "")
    print(f"    {label}: {shown}" + (" [OK]" if ok else ""), flush=True)
    return ok


def _snap(cap, name):
    """Saves what the 3DS is showing right now, so a failure can be seen,
    not guessed at. The folder only ever holds the latest attempt."""
    global _debug_step
    try:
        frame = cap.frame()
        if hasattr(frame, "shape"):
            _debug_step += 1
            os.makedirs(_debug_attempt_dir, exist_ok=True)
            cv2.imwrite(os.path.join(_debug_attempt_dir, f"{_debug_step:02d}_{name}.png"), frame)
    except Exception:
        pass  # a debug picture must never break the bot


def _reset_debug():
    """Starts a new timestamped folder for this attempt and deletes all but
    the newest DEBUG_KEEP attempt folders."""
    global _debug_step, _debug_attempt_dir
    _debug_step = 0
    _debug_attempt_dir = os.path.join(DEBUG_DIR, time.strftime("attempt_%Y%m%d_%H%M%S"))
    try:
        old = sorted(d for d in os.listdir(DEBUG_DIR) if d.startswith("attempt_"))
        for d in old[:-(DEBUG_KEEP - 1)] if len(old) >= DEBUG_KEEP else []:
            shutil.rmtree(os.path.join(DEBUG_DIR, d), ignore_errors=True)
    except FileNotFoundError:
        pass


def _gone(cap, cfg, target, heartbeat):
    """True only if two separate frames, a moment apart, both show the
    target has gone (e.g. the START menu closed because A worked)."""
    heartbeat()
    key, ref, label = target
    time.sleep(MENU_SETTLE)
    s1 = match_score(cap.frame(), cfg[key], ref)
    s2 = None
    if s1 < MENU_MATCH_THRESHOLD:
        time.sleep(CONFIRM_GAP)
        s2 = match_score(cap.frame(), cfg[key], ref)
    ok = s2 is not None and s2 < MENU_MATCH_THRESHOLD
    shown = f"{s1:.2f}" + (f"/{s2:.2f}" if s2 is not None else "")
    print(f"    {label} (want it gone): {shown}" + (" [GONE]" if ok else " [still there]"),
          flush=True)
    return ok


_arrow_cache = {}


def _arrow_template(cfg):
    """Cuts the arrow's exact shape out of the two calibration pictures:
    ref_menu_pokemon.png (arrow on POKEMON) minus ref_menu_pokemon_off.png
    (same spot, no arrow) leaves just the arrow. Returns (template, x, y)
    with x, y the arrow's position inside menu_pokemon_roi, or None."""
    if "t" in _arrow_cache:
        return _arrow_cache["t"]
    result = None
    on = cv2.imread(CURSOR_POKEMON[1], cv2.IMREAD_GRAYSCALE)
    off = cv2.imread(POKEMON_OFF_REF, cv2.IMREAD_GRAYSCALE)
    if on is not None and off is not None and on.shape == off.shape:
        ys, xs = (cv2.absdiff(on, off) > 60).nonzero()
        if xs.size >= 6:
            x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
            result = (on[y0:y1, x0:x1], int(x0), int(y0))
    _arrow_cache["t"] = result
    return result


def _arrow_offset(cap, cfg):
    return arrow_offset_in(cap.frame(), cfg)


def arrow_offset_in(frame, cfg):
    """Where is the START-menu arrow compared to the POKEMON row? Returns
    pixels (negative = above POKEMON, positive = below), or None if it
    can't be found. Searches only the arrow column of the menu."""
    t = _arrow_template(cfg)
    if t is None:
        return None
    tmpl, ax, ay = t
    th, tw = tmpl.shape
    pr, mr = cfg["menu_pokemon_roi"], cfg["start_menu_roi"]
    arrow_x, arrow_y_at_pokemon = pr["left"] + ax, pr["top"] + ay
    if not hasattr(frame, "shape"):
        return None
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    pad = max(4, tw)
    x0, x1 = max(0, arrow_x - pad), min(frame.shape[1], arrow_x + tw + pad)
    y0, y1 = max(0, mr["top"]), min(frame.shape[0], mr["top"] + mr["height"])
    strip = frame[y0:y1, x0:x1]
    if strip.shape[0] < th or strip.shape[1] < tw:
        return None
    _, score, _, loc = cv2.minMaxLoc(cv2.matchTemplate(strip, tmpl, cv2.TM_CCOEFF_NORMED))
    if score < 0.6:
        return None
    return (y0 + loc[1]) - arrow_y_at_pokemon


def _cursor_on_pokemon(cap, cfg, heartbeat):
    """The "POKEMON" text alone can score well even when the arrow is on
    another row (seen in a real run: 0.84 while an A then opened the
    POKEDEX). So compare against BOTH references -- cursor on POKEMON vs.
    cursor one row up -- and only accept if it clearly looks more like
    the arrow-present one, on two separate frames."""
    heartbeat()
    key = CURSOR_POKEMON[0]
    looks = []
    for i in range(2):
        time.sleep(MENU_SETTLE if i == 0 else CONFIRM_GAP)
        frame = cap.frame()
        on = match_score(frame, cfg[key], CURSOR_POKEMON[1])
        off = match_score(frame, cfg[key], POKEMON_OFF_REF)
        looks.append((on, off))
        if not (on >= MENU_MATCH_THRESHOLD and on - off >= CURSOR_MARGIN):
            break
    ok = len(looks) == 2 and all(on >= MENU_MATCH_THRESHOLD and on - off >= CURSOR_MARGIN
                                 for on, off in looks)
    shown = "  ".join(f"arrow {on:.2f} vs no-arrow {off:.2f}" for on, off in looks)
    print(f"    cursor on POKEMON: {shown}" + (" [OK]" if ok else ""), flush=True)
    return ok


def _tap(pad, button, name):
    print(f"  -> {name}", flush=True)
    pad.tap(button, hold=A_HOLD if button == Button.A else 0.1, gap=0.2)


def _open_start_menu(pad, cap, cfg, heartbeat):
    for _ in range(3):
        _tap(pad, Button.B, "B (make sure no menu is open)")
        time.sleep(CLOSED_WAIT)
        _tap(pad, Button.START, "START")
        if _looks(cap, cfg, START_MENU_OPEN, heartbeat):
            return True
    return False


MAX_NAV_STEPS = 10


def _cursor_to_pokemon(pad, cap, cfg, heartbeat):
    """Moves the START-menu cursor onto POKEMON the short way: finds where
    the arrow actually is and presses DOWN if it's above POKEMON or UP if
    it's below, re-checking after every press -- never looping round the
    whole menu past SAVE. If the arrow can't be found, falls back to DOWN
    (the menu tends to reopen on POKEDEX, one row above)."""
    t = _arrow_template(cfg)
    half_row = max(3, t[0].shape[0] // 2) if t else 3
    for _ in range(MAX_NAV_STEPS):
        if _cursor_on_pokemon(cap, cfg, heartbeat):
            return True
        dy = _arrow_offset(cap, cfg)
        if dy is None:
            print("    arrow position: not found -- trying DOWN", flush=True)
            _tap(pad, Button.DOWN, "DOWN")
        elif dy < -half_row:
            print(f"    arrow is ABOVE POKEMON ({dy:+d}px)", flush=True)
            _tap(pad, Button.DOWN, "DOWN")
        elif dy > half_row:
            print(f"    arrow is BELOW POKEMON ({dy:+d}px)", flush=True)
            _tap(pad, Button.UP, "UP")
        else:
            print("    arrow looks level with POKEMON -- checking again", flush=True)
    return False


# ---------------------------------------------------------------- fast path
# Single-frame tests (the fast path watches the stream with these).

def menu_open(frame, cfg):
    return match_score(frame, cfg[START_MENU_OPEN[0]], START_MENU_OPEN[1]) >= MENU_MATCH_THRESHOLD


def on_pokemon(frame, cfg):
    on = match_score(frame, cfg[CURSOR_POKEMON[0]], CURSOR_POKEMON[1])
    off = match_score(frame, cfg[CURSOR_POKEMON[0]], POKEMON_OFF_REF)
    return on >= MENU_MATCH_THRESHOLD and on - off >= CURSOR_MARGIN


def sweet_visible(frame, cfg):
    return match_score(frame, cfg[CURSOR_SWEET[0]], CURSOR_SWEET[1]) >= MENU_MATCH_THRESHOLD


def _fast_menu_path(pad, cap, cfg, in_battle, hb):
    """START -> POKEMON -> first Pokemon -> SWEET SCENT, reacting to the
    stream instead of fixed waits. Only called from a known state (the
    overworld right after a confirmed flee), so no menu can be open.
    Returns True (battle started), False (safe to retry), or None (unsure
    -- caller falls back to the slow, fully checked path).

    Tuned from a real run (4 FPS stream, presses sometimes ~1 s late):
    "confirmed" means true on every look for CONFIRM_SPAN, and a press is
    never repeated sooner than RETRY_AFTER."""
    ok = lambda test: (lambda f: test(f, cfg))
    not_ = lambda test: (lambda f: not test(f, cfg))

    # Wait until the overworld has fully faded in and sat still for 0.5 s
    # (START pressed mid-fade was ignored in the real run).
    before = watch.wait_still(cap, 0.5, 5.0, heartbeat=hb)
    if before is None or menu_open(before, cfg):
        print("    overworld not settled -- using the slow path.", flush=True)
        return None

    # START -- the menu must appear AFTER the press. Only press it again
    # after a long gap, so a late START and its retry can't open and then
    # close the menu.
    frame = None
    for attempt in range(1, 4):
        watch.tap(pad, Button.START, "START" if attempt == 1 else f"START (again, {attempt}/3)")
        frame = watch_for(cap, ok(menu_open), 2.5, before=before, heartbeat=hb)
        if frame is not None:
            break
        before = cap.frame()
        if menu_open(before, cfg):          # it just opened after all
            confirmed, frame = watch.holds(cap, ok(menu_open), heartbeat=hb)
            if confirmed:
                break
            return None
    else:
        print("    START menu didn't appear -- using the slow path.", flush=True)
        return None

    # Cursor onto POKEMON, the short way.
    t = _arrow_template(cfg)
    half_row = max(3, t[0].shape[0] // 2) if t else 3
    for _ in range(MAX_NAV_STEPS):
        confirmed, frame = watch.holds(cap, ok(on_pokemon), heartbeat=hb)
        if confirmed:
            break
        if not menu_open(frame, cfg):
            # Not showing the START menu: NEVER press a direction on that
            # basis -- just look again.
            time.sleep(watch.POLL)
            continue
        dy = arrow_offset_in(frame, cfg)
        if dy is not None and abs(dy) <= half_row:
            continue                        # level with POKEMON: look again
        button, name = (Button.UP, "UP") if (dy is not None and dy > 0) else (Button.DOWN, "DOWN")
        watch.tap(pad, button, name)
        moved = watch_for(cap, ok(on_pokemon), watch.RETRY_AFTER, before=frame, heartbeat=hb)
        if moved is not None:
            frame = moved
            break
    else:
        _snap(cap, "fast_cursor_not_on_POKEMON")
        return None
    print("    cursor on POKEMON [OK]", flush=True)

    # A on POKEMON -- confirm the START menu actually closed.
    for attempt in range(1, MAX_A_TRIES + 1):
        watch.tap(pad, Button.A, f"A (verified: POKEMON), try {attempt}")
        if watch_for(cap, not_(menu_open), watch.RETRY_AFTER, before=frame, heartbeat=hb) is not None:
            break
        confirmed, frame = watch.holds(cap, ok(on_pokemon), heartbeat=hb)
        if not confirmed:
            _snap(cap, "fast_after_A_on_POKEMON")
            return None
    else:
        return None

    # Party screen: past the fade and still, then A on the first Pokemon
    # (no checks there, by design).
    party = watch.wait_still(cap, 0.3, 3.0, heartbeat=hb)
    if party is None:
        _snap(cap, "fast_party_not_ready")
        return None
    watch.tap(pad, Button.A, "A (first Pokemon)")

    frame = watch_for(cap, ok(sweet_visible), 2.0, before=party, heartbeat=hb)
    if frame is None:
        _snap(cap, "fast_SWEET_SCENT_not_found")
        print("  SWEET SCENT didn't appear -- backing out with B.", flush=True)
        close_menus(pad)
        return False
    for attempt in range(1, MAX_A_TRIES + 1):
        watch.tap(pad, Button.A, f"A (verified: SWEET SCENT), try {attempt}")
        if watch_for(cap, not_(sweet_visible), watch.RETRY_AFTER, before=frame, heartbeat=hb) is not None:
            break
        confirmed, frame = watch.holds(cap, ok(sweet_visible), heartbeat=hb)
        if not confirmed:
            break          # it moved on after all
    else:
        close_menus(pad)
        return False

    # "<POKEMON> used SWEET SCENT!" waits for a button: B clears it and is
    # harmless on the overworld, during the transition, and on "Wild X
    # appeared!". Keep pressing it until the battle shows up.
    end = time.time() + SWEET_SCENT_TIMEOUT
    presses = 0
    while time.time() < end:
        if in_battle(cap, cfg):
            print(f"    battle started ({presses} B presses to clear the message)", flush=True)
            return True
        if ntr_status.is_down():
            # A dip (common during battle transitions): don't press into it,
            # just keep watching. A real freeze runs out the timeout and the
            # main loop handles it.
            time.sleep(0.25)
            continue
        watch.tap(pad, Button.B, "B", log=False)
        presses += 1
        time.sleep(0.15)
    _snap(cap, "fast_no_encounter")
    print("  No encounter after Sweet Scent -- backing out with B.", flush=True)
    close_menus(pad)
    return False


def close_menus(pad):
    for _ in range(4):
        _tap(pad, Button.B, "B (back out)")
        time.sleep(0.6)


def trigger_encounter(pad, cap, cfg, in_battle, heartbeat=lambda: None, fast=False):
    """Uses Sweet Scent. Returns True once a battle has started, False if
    anything didn't go as expected (menus are then closed with B).
    fast=True (only right after a confirmed flee, when no menu can be
    open) reacts to the stream as it updates; if anything is unclear it
    falls through to the slow path below, which checks everything with
    fixed waits."""
    _reset_debug()
    if fast:
        print("  Using Sweet Scent (fast):", flush=True)
        result = _fast_menu_path(pad, cap, cfg, in_battle, heartbeat)
        if result is not None:
            return result
        print("  Falling back to the slow path:", flush=True)
        close_menus(pad)
    print("  Using Sweet Scent:", flush=True)
    if not _open_start_menu(pad, cap, cfg, heartbeat):
        print("  Couldn't open the START menu -- backing out with B.", flush=True)
        close_menus(pad)
        return False
    _snap(cap, "start_menu_open")
    if not _cursor_to_pokemon(pad, cap, cfg, heartbeat):
        print("  Couldn't get the cursor onto POKEMON -- backing out with B.", flush=True)
        close_menus(pad)
        return False
    # A on POKEMON, then confirm it actually worked (START menu gone).
    # If the menu is still there with the cursor still on POKEMON, the
    # press didn't land -- pressing A again is safe. Two "gone" checks
    # before any re-press, so a slow party-screen load or a stale frame
    # can't cause a double press.
    opened_party = False
    for attempt in range(1, MAX_A_TRIES + 1):
        _tap(pad, Button.A, f"A (verified: POKEMON), try {attempt}/{MAX_A_TRIES}")
        _snap(cap, f"after_A_on_POKEMON_try{attempt}")
        if _gone(cap, cfg, START_MENU_OPEN, heartbeat) or \
           _gone(cap, cfg, START_MENU_OPEN, heartbeat):
            opened_party = True
            break
        if not _cursor_on_pokemon(cap, cfg, heartbeat):
            break   # menu still open but cursor moved: don't guess
    if not opened_party:
        print("  The party screen never opened -- backing out with B. "
              f"Screenshots saved in {DEBUG_DIR}/.", flush=True)
        close_menus(pad)
        return False

    _snap(cap, "party_screen")
    _tap(pad, Button.A, "A (first Pokemon)")          # no checks, by design
    _snap(cap, "after_A_on_first_Pokemon")

    if not (_looks(cap, cfg, CURSOR_SWEET, heartbeat) or
            _looks(cap, cfg, CURSOR_SWEET, heartbeat)):
        _snap(cap, "SWEET_SCENT_not_found")
        print("  SWEET SCENT isn't under the cursor -- backing out with B. "
              f"Screenshots saved in {DEBUG_DIR}/.", flush=True)
        close_menus(pad)
        return False
    # A on SWEET SCENT -- and confirm it took effect. (Crystal's code shows
    # Sweet Scent can't fail on a tile where wild Pokemon appear, so a lost
    # press was the usual reason for "no encounter"; the fast path already
    # checked this.)
    for attempt in range(1, MAX_A_TRIES + 1):
        _tap(pad, Button.A, f"A (verified: SWEET SCENT), try {attempt}/{MAX_A_TRIES}")
        _snap(cap, f"after_A_on_SWEET_SCENT_{attempt}")
        if _gone(cap, cfg, CURSOR_SWEET, heartbeat):
            break
        if not (_looks(cap, cfg, CURSOR_SWEET, heartbeat) and
                _looks(cap, cfg, CURSOR_SWEET, heartbeat)):
            break                     # the screen moved on after all
    else:
        _snap(cap, "SWEET_SCENT_A_never_took")
        print("  A on SWEET SCENT never took effect -- backing out with B.", flush=True)
        close_menus(pad)
        return False

    # "<POKEMON> used SWEET SCENT!" waits for a button press before the
    # encounter starts. B clears it, and is harmless everywhere else here
    # (does nothing on the overworld or on "Wild X appeared!").
    deadline = time.time() + SWEET_SCENT_TIMEOUT
    while time.time() < deadline:
        time.sleep(1.0)
        if in_battle(cap, cfg):       # in_battle also re-arms the watchdog
            return True
        _tap(pad, Button.B, "B (clear the Sweet Scent message)")
    _snap(cap, "no_encounter")
    print("  No encounter started after Sweet Scent -- backing out with B. "
          f"Screenshots saved in {DEBUG_DIR}/.", flush=True)
    close_menus(pad)
    return False
