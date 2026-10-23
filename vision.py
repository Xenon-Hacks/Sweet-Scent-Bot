"""
vision.py

Template-matching helpers (battle detection, menu and cursor checks) used
by sweet_scent_bot.py. Shiny detection lives in shiny_flash.py.

Frames come from `cap.frame()` -- in practice shared_frame.SharedFrameCapture,
which reads NTR-VC's shared memory, so NTR-VC can be minimised.
"""

import time

import cv2
import numpy as np


def wait_until_stable(cap, samples: int = 3, interval: float = 0.35,
                       max_wait: float = 6.0, diff_threshold: float = 3.0) -> np.ndarray:
    """Waits until the screen stops visibly changing -- i.e. an intro
    animation or typewriter-effect text has finished rendering -- rather
    than guessing a fixed delay. Gives up and returns the latest frame
    anyway after `max_wait` seconds so a stuck loop never hangs forever.
    Returns the final (settled, or last-seen) frame."""
    start = time.time()
    prev = None
    stable_count = 0
    frame = cap.frame()
    while time.time() - start < max_wait:
        frame = cap.frame()
        if prev is not None:
            diff = float(np.mean(cv2.absdiff(frame, prev)))
            if diff < diff_threshold:
                stable_count += 1
                if stable_count >= samples:
                    return frame
            else:
                stable_count = 0
        prev = frame
        time.sleep(interval)
    return frame


def crop(frame: np.ndarray, roi: dict) -> np.ndarray:
    """roi = {"left":, "top":, "width":, "height":}, relative to `frame`."""
    x, y, w, h = roi["left"], roi["top"], roi["width"], roi["height"]
    return frame[y:y + h, x:x + w]


def match_score(frame: np.ndarray, roi: dict, reference_path: str) -> float:
    """Raw normalized template-match score (0-1, higher = closer match) of
    `frame` cropped to `roi` against a saved reference image."""
    ref = cv2.imread(reference_path)
    if ref is None:
        raise FileNotFoundError(
            f"{reference_path} not found -- did calibrate.py finish?")
    patch = crop(frame, roi)
    if patch.shape[:2] != ref.shape[:2]:
        patch = cv2.resize(patch, (ref.shape[1], ref.shape[0]))
    result = cv2.matchTemplate(patch, ref, cv2.TM_CCOEFF_NORMED)
    _, score, _, _ = cv2.minMaxLoc(result)
    return float(score)


def looks_like(frame: np.ndarray, roi: dict, reference_path: str,
                threshold: float = 0.85) -> bool:
    """True if `frame`'s `roi` scores at or above `threshold` against a
    saved reference image."""
    return match_score(frame, roi, reference_path) >= threshold
