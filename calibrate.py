"""
calibrate.py -- one-time setup helper. Run this BEFORE sweet_scent_bot.py.

It reads the game picture from NTR-VC (the frame-sharing NTRViewer-HR), so
NTR-VC must be running and connected to the 3DS -- but it can be minimised
or behind other windows. It walks you through boxing a few small reference
images: the battle screen, the RUN cursor, and the Sweet Scent menus.
Everything is written to config.json plus a few .png files in this folder.
Shiny detection needs no calibration (it watches for the shiny animation's
flash, see shiny_flash.py).

Usage:
    py calibrate.py            full setup (skips steps that are already done)
    py calibrate.py --all      redo every step from scratch
    py calibrate.py --battle   redo one step: the battle indicator
    py calibrate.py --cursor   redo one step: the RUN cursor
    py calibrate.py --menus    redo one step: the Sweet Scent menus
"""

import argparse
import json
import sys

import cv2

import shared_frame

CONFIG_PATH = "config.json"
REGION_KEYS = ["battle_indicator_roi", "cursor_run_roi", "start_menu_roi",
               "menu_pokemon_roi", "sweet_scent_roi"]
# Keys from older versions: screen-capture calibrations. They were measured
# in a different picture, so they're dropped rather than reused.
OBSOLETE_KEYS = ["capture_region", "sprite_roi", "frame_source"]


def ask(prompt):
    """Waits for ENTER. The picture comes from NTR-VC's shared memory, so
    it doesn't matter which window is in front when you press it."""
    input(prompt)


def select_region(prompt, img):
    print(prompt)
    print("Drag a box, then press ENTER or SPACE to confirm (C to cancel).")
    r = cv2.selectROI("calibrate - " + prompt, img, showCrosshair=True)
    cv2.waitKey(1)  # let the window finish one more redraw before closing --
                     # skipping this can crash/hang cv2's GUI teardown on Windows
    cv2.destroyAllWindows()
    cv2.waitKey(1)
    x, y, w, h = (int(v) for v in r)
    print(f"Got a {w}x{h} box at ({x}, {y}).")
    return x, y, w, h


def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"Saved {CONFIG_PATH}")


_cap = None


def grab_frame(cfg):
    """The current game picture (upright, 1600x960) from NTR-VC."""
    global _cap
    if _cap is None:
        _cap = shared_frame.SharedFrameCapture(rotation=cfg.get("shared_rotation", 1))
        if not shared_frame.wait_until_available(_cap, timeout=15.0):
            raise SystemExit(
                "No frames from NTR-VC. Start NTR-VC (the frame-sharing "
                "NTRViewer-HR), connect it to the 3DS, and run this again. "
                "(py test_shared_frame.py checks the connection.)")
    return _cap.frame()


def calibrate_battle_indicator(cfg):
    """A small region of the game picture that looks visibly
    different on the overworld vs. mid-battle -- e.g. a corner where the
    HP box appears. Captured twice: once now (overworld), once after you
    walk into a battle."""
    ask("Get the game on the OVERWORLD, then press ENTER here: ")
    frame = grab_frame(cfg)
    x, y, w, h = select_region(
        "On the OVERWORLD right now: drag a box around a spot that will "
        "clearly change once a battle starts (e.g. where the HP box "
        "appears).", frame)
    if w == 0 or h == 0:
        print("Empty selection, aborting.")
        sys.exit(1)
    roi = {"left": x, "top": y, "width": w, "height": h}
    cfg["battle_indicator_roi"] = roi
    cv2.imwrite("ref_overworld.png", frame[y:y + h, x:x + w])
    print("Saved ref_overworld.png.")

    ask(
        "Now walk into a wild battle (any Pokemon). Once you're in it, "
        "press ENTER here: ")
    frame2 = grab_frame(cfg)
    cv2.imwrite("ref_battle.png", frame2[y:y + h, x:x + w])
    print("Saved ref_battle.png.")
    save_config(cfg)
    return cfg


def calibrate_run_cursor(cfg):
    """A small, tight crop around the "> RUN" cursor position specifically
    -- this is what sweet_scent_bot.py checks BEFORE ever pressing the
    confirming A, so it never selects FIGHT (and a move) by mistake."""
    ask(
        "Get into a wild battle and navigate the cursor to RUN BY HAND "
        "(don't confirm it), so the little arrow is sitting right next "
        "to RUN. Once it's there, press ENTER: ")
    frame = grab_frame(cfg)
    x, y, w, h = select_region(
        "Drag a TIGHT box around the cursor arrow + 'RUN' text together "
        "-- small and precise is better than loose here.", frame)
    if w == 0 or h == 0:
        print("Empty selection, aborting.")
        sys.exit(1)
    cfg["cursor_run_roi"] = {"left": x, "top": y, "width": w, "height": h}
    cv2.imwrite("ref_cursor_run.png", frame[y:y + h, x:x + w])
    print("Saved ref_cursor_run.png.")
    save_config(cfg)
    return cfg


def _capture_box(cfg, prompt, roi_key, ref_file, box_hint):
    ask(prompt)
    frame = grab_frame(cfg)
    x, y, w, h = select_region(box_hint, frame)
    if w == 0 or h == 0:
        print("Empty selection, aborting.")
        sys.exit(1)
    cfg[roi_key] = {"left": x, "top": y, "width": w, "height": h}
    cv2.imwrite(ref_file, frame[y:y + h, x:x + w])
    print(f"Saved {ref_file}.")
    save_config(cfg)


def calibrate_menus(cfg):
    """Four reference crops for the Sweet Scent menu path, captured in
    one trip through the menus starting from the overworld."""
    print("\nSweet Scent menu calibration. Stand on a tile where wild "
          "Pokemon appear, on the overworld with no menu open, then follow "
          "each prompt.")
    _capture_box(
        cfg,
        "1/4: Press START by hand and move the cursor to POKEMON. "
        "Then press ENTER here: ",
        "start_menu_roi", "ref_start_menu.png",
        "Drag a box around the WHOLE START menu (the white box with all "
        "8 items).")
    _capture_box(
        cfg,
        "2/4: Same screen, cursor still on POKEMON. Press ENTER here: ",
        "menu_pokemon_roi", "ref_menu_pokemon.png",
        "Drag a TIGHT box around the cursor arrow + 'POKEMON' text together.")
    ask(
        "3/4: Press UP once on the 3DS so the cursor is on POKEDEX (NOT on "
        "POKEMON). Then press ENTER here: ")
    frame = grab_frame(cfg)
    r = cfg["menu_pokemon_roi"]
    cv2.imwrite("ref_menu_pokemon_off.png",
                frame[r["top"]:r["top"] + r["height"], r["left"]:r["left"] + r["width"]])
    print("Saved ref_menu_pokemon_off.png (same box, cursor elsewhere) -- "
          "lets the bot tell 'arrow on POKEMON' from just the POKEMON text.")
    _capture_box(
        cfg,
        "4/4: Press DOWN to put the cursor back on POKEMON, press A to open "
        "the party screen, then A again on your FIRST Pokemon, so its menu "
        "is open with the cursor on SWEET SCENT. Then press ENTER here: ",
        "sweet_scent_roi", "ref_sweet_scent.png",
        "Drag a TIGHT box around the cursor arrow + 'SWEET SCENT' text.")
    print("\nMenu calibration done -- press B on the 3DS until you're back "
          "on the overworld.")
    return cfg


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true",
                         help="redo every step from scratch")
    parser.add_argument("--battle", action="store_true",
                         help="redo step 1 (battle indicator) only")
    parser.add_argument("--cursor", action="store_true",
                         help="redo step 2 (RUN cursor) only")
    parser.add_argument("--menus", action="store_true",
                         help="redo step 3 (Sweet Scent menus) only")
    args = parser.parse_args()

    try:
        cfg = load_config()
        if "capture_region" in cfg or cfg.get("frame_source") == "screen":
            # An older, screen-capture setup: its regions were measured in a
            # different picture and don't carry over.
            print("This config.json was made for screen capture, which is no "
                  "longer used. Starting the setup over for NTR-VC.")
            for key in REGION_KEYS:
                cfg.pop(key, None)
        if args.all:
            for key in REGION_KEYS:
                cfg.pop(key, None)
        for key in OBSOLETE_KEYS:
            cfg.pop(key, None)
        cfg["frame_source"] = "shared"

        if args.battle:
            cfg = calibrate_battle_indicator(cfg)
        elif args.cursor:
            cfg = calibrate_run_cursor(cfg)
        elif args.menus:
            cfg = calibrate_menus(cfg)
        else:
            # Only run whichever steps aren't already saved, so re-running
            # this after an interruption doesn't force you to redo
            # earlier steps that already worked.
            if "battle_indicator_roi" not in cfg:
                cfg = calibrate_battle_indicator(cfg)
            else:
                print("battle_indicator_roi already set -- skipping (use "
                      "--battle to redo it).")
            if "cursor_run_roi" not in cfg:
                cfg = calibrate_run_cursor(cfg)
            else:
                print("cursor_run_roi already set -- skipping (use "
                      "--cursor to redo it).")
            if "sweet_scent_roi" not in cfg:
                cfg = calibrate_menus(cfg)
            else:
                print("Sweet Scent menus already set -- skipping (use "
                      "--menus to redo them).")
            print("\nAll regions calibrated. Run sweet_scent_bot.py next.")
        save_config(cfg)
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        input("\nDone -- press ENTER to close this window.")
