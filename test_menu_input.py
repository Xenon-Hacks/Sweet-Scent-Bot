"""
test_menu_input.py -- measures how reliably button presses reach the game
on the START menu, which is where the Sweet Scent bot loses presses.

What it does:
  * opens the START menu (the bot's own fully checked routine),
  * presses ONLY DOWN/UP inside the menu -- never A -- and times each press
    against the arrow actually moving on screen (using your calibration),
  * holds each press 0.25 s (just under the menu's auto-repeat) and
    alternates press by press between with and without a "keepalive" (a
    steady stream of no-buttons packets in the background, in case the
    3DS's Wi-Fi dozes while the picture doesn't change) -- alternating
    means both face the same Wi-Fi conditions,
  * prints a table, then closes the menu with B.

Safety: before every press it checks the START menu is open; if the menu
is ever not open, it stops immediately -- a direction is never sent to
the overworld.

Run from the overworld with no menu open:
    py test_menu_input.py --ip 192.168.4.31
Takes about 2-3 minutes (30 presses). Close InputRedirectionClient-Qt first.
"""

import argparse
import statistics
import threading
import time

from luma_input import Luma3DSInput, Button
import sweet_scent as ss
from sweet_scent_bot import load_config, make_capture

HOLD = 0.25         # just under the menu's auto-repeat (0.4 s moved 2 rows)
TRIALS = 30         # alternating keepalive off/on, so both face the same Wi-Fi
SETTLE = 1.2        # arrow must sit still this long before the next press
TIMEOUT = 3.0       # a press that hasn't moved the arrow by then = lost
ON_TIME = 0.35      # moved within this (includes stream delay) = on time


class Keepalive:
    """Sends the current (no-buttons) state ~50 times a second while no
    press is being made."""
    def __init__(self, pad, lock):
        self.pad, self.lock = pad, lock
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        while not self.stop.is_set():
            with self.lock:
                self.pad.send()
            time.sleep(0.02)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join()


def arrow_now(cap, cfg):
    frame = cap.frame()
    if not ss.menu_open(frame, cfg):
        return None, False
    return ss.arrow_offset_in(frame, cfg), True


def wait_settled(cap, cfg):
    """Arrow position that hasn't changed for SETTLE seconds."""
    last, since = None, time.time()
    end = time.time() + 10
    while time.time() < end:
        pos, is_open = arrow_now(cap, cfg)
        if not is_open:
            return None, False
        if pos != last:
            last, since = pos, time.time()
        elif time.time() - since >= SETTLE and pos is not None:
            return pos, True
        time.sleep(0.03)
    return last, True


def one_press(pad, cap, cfg, lock, hold):
    start_pos, is_open = wait_settled(cap, cfg)
    if not is_open or start_pos is None:
        raise RuntimeError("START menu not open (or arrow not found) -- stopping for safety")
    button = Button.DOWN if start_pos <= 0 else Button.UP     # stay near POKEMON
    def press():
        with lock:
            pad.tap(button, hold=hold, gap=0.05, resend=max(3, int(hold / 0.03)))
    presser = threading.Thread(target=press, daemon=True)
    t0 = time.time()
    presser.start()                 # watch the screen WHILE the button is held
    first_move = None
    end = t0 + TIMEOUT
    while time.time() < end:
        pos, is_open = arrow_now(cap, cfg)
        if not is_open:
            raise RuntimeError("START menu closed unexpectedly -- stopping for safety")
        if pos is not None and pos != start_pos and first_move is None:
            first_move = time.time() - t0
        time.sleep(0.02)
    presser.join()
    final_pos, _ = wait_settled(cap, cfg)
    return first_move, start_pos, final_pos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip", required=True)
    args = ap.parse_args()
    cfg = load_config()
    cap = make_capture(cfg)
    pad = Luma3DSInput(args.ip)
    lock = threading.Lock()
    results = {}
    try:
        print("Opening the START menu (checked)...")
        if not ss._open_start_menu(pad, cap, cfg, lambda: None):
            print("Couldn't open the START menu -- nothing tested.")
            return
        row = None
        results = {"keepalive off": [], "keepalive ON ": []}
        for i in range(TRIALS):
            keep = i % 2 == 1
            label = "keepalive ON " if keep else "keepalive off"
            ctx = Keepalive(pad, lock) if keep else None
            if ctx:
                ctx.__enter__()
                time.sleep(0.5)             # let the keepalive run before the press
            try:
                first_move, a, b = one_press(pad, cap, cfg, lock, HOLD)
            finally:
                if ctx:
                    ctx.__exit__(None, None, None)
            steps = 0 if b == a else None
            if b != a and a is not None and b is not None:
                row = row or abs(b - a)
                steps = round(abs(b - a) / row)
            results[label].append((first_move, steps))
            shown = "LOST" if first_move is None else f"{first_move:.2f}s"
            print(f"  press {i + 1:2d} ({label}): {shown:>6}  moved {steps} row(s)")
    except RuntimeError as e:
        print(f"\n*** {e} ***")
    finally:
        print("\nClosing the menu with B.")
        for _ in range(3):
            pad.tap(Button.B, hold=0.2, gap=0.4)
        pad.release_all()
        pad.send()
        pad.return_control()
        pad.close()

    print("\n=== RESULTS (send me this table) ===")
    print(f"{'condition':30s} {'on time':>8} {'late':>5} {'lost':>5} {'double':>7} {'median delay':>13}")
    for label, rows in results.items():
        delays = [d for d, _ in rows if d is not None]
        on_time = sum(1 for d in delays if d <= ON_TIME)
        late = sum(1 for d in delays if d > ON_TIME)
        lost = sum(1 for d, _ in rows if d is None)
        double = sum(1 for _, s in rows if s is not None and s >= 2)
        med = f"{statistics.median(delays):.2f}s" if delays else "-"
        print(f"{label:30s} {on_time:8d} {late:5d} {lost:5d} {double:7d} {med:>13}")


if __name__ == "__main__":
    main()
