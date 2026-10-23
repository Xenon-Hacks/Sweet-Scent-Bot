"""
test_flee.py -- runs sweet_scent_bot.py's REAL flee() function once
(same code path, same cursor-verification safety), so you can confirm
it's working before trusting it to run unattended.

Requires calibrate.py to have already saved cursor_run_roi (the
"--cursor" step) in addition to the usual
battle_indicator_roi -- flee() checks the actual cursor position before
it will ever press the button that confirms RUN, and can't do that
without ref_cursor_run.png.

Walk into a wild battle BY HAND first (any Pokemon), with the
"Wild X appeared!" message showing, THEN run:

    py test_flee.py --ip 192.168.4.31
"""

import argparse
import json

from luma_input import Luma3DSInput
from sweet_scent_bot import make_capture
from sweet_scent_bot import flee


def load_test_config():
    try:
        with open("config.json") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        print("config.json not found -- run calibrate.py first.")
        raise SystemExit(1)
    for key in ("battle_indicator_roi", "cursor_run_roi"):
        if key not in cfg:
            print(f"config.json is missing '{key}'. Run calibrate.py, or "
                  f"just the matching step (e.g. py calibrate.py --cursor).")
            raise SystemExit(1)
    return cfg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", required=True)
    args = parser.parse_args()

    cfg = load_test_config()
    cap = make_capture(cfg)
    pad = Luma3DSInput(args.ip)

    print("Get into a wild battle BY HAND right now (any Pokemon), with "
          "the 'Wild X appeared!' message showing on screen.")
    input("Press ENTER once that's up and you're watching your 3DS: ")

    try:
        print("Running the real flee() function...\n")
        ok = flee(pad, cap, cfg)
        if ok:
            print("\nflee() reports success -- confirm you're actually "
                  "back on the overworld.")
        else:
            print("\nflee() reports it could NOT confirm the cursor "
                  "reached RUN, so it did NOT press the confirming A. "
                  "Check your 3DS: you should be somewhere harmless "
                  "(still on text, or on the main menu) -- NOT mid-move.")
    finally:
        pad.close()
        print("Released control back to the physical buttons.")


if __name__ == "__main__":
    main()
