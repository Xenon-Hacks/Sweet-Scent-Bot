"""A 3DS that stops streaming (Connection Quality 0%) no longer stops the
bot until ENTER: it waits, presses nothing while the picture is gone,
alerts once (and once more after 20 minutes), then backs out of any menu
and carries on. NTR-VC closing or freezing still pauses for you."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sweet_scent_bot as bot  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t

    def sleep(self, s):
        self.t += s


class Pad:
    def __init__(self):
        self.presses = []

    def tap(self, button, **kw):
        self.presses.append(button)

    def release_all(self):
        pass

    def send(self):
        pass

    def return_control(self):
        pass


def run(monkeypatch, down_for, reason="0%"):
    clock = Clock()
    monkeypatch.setattr(bot.time, "time", clock.time)
    monkeypatch.setattr(bot.time, "sleep", clock.sleep)
    start = clock.t
    up_at = start + 30 + down_for          # 30 s inside stream_dead first

    def down_reason():
        return reason if clock.t < up_at else None
    monkeypatch.setattr(bot.ntr_status, "down_reason", down_reason)

    def stream_dead(heartbeat=None):
        if down_reason() is None:
            return False
        clock.t += 30
        bot.ntr_status.last_reason = down_reason()
        return True
    monkeypatch.setattr(bot.ntr_status, "stream_dead", stream_dead)

    alerts, pauses = [], []
    monkeypatch.setattr(bot.alarm, "notify",
                        lambda cfg, msg, pic=None: alerts.append(msg) or (lambda t=0: None))
    monkeypatch.setattr(bot, "pause_for_user",
                        lambda pad, msg, **kw: (pauses.append(msg), setattr(clock, "t", up_at)))
    monkeypatch.setattr(bot, "_heartbeat", lambda: None)
    pad = Pad()
    assert bot.wait_for_live_stream(pad) is True
    return pad, alerts, pauses, clock.t - start


def test_short_drop_resumes_by_itself(monkeypatch):
    pad, alerts, pauses, took = run(monkeypatch, down_for=11 * 60)
    assert pauses == []
    assert len(alerts) == 1 and "Stream dropped" in alerts[0]
    assert pad.presses == [bot.Button.B] * bot.CLEAR_MENU_PRESSES
    assert took >= 30 + 11 * 60 + bot.STREAM_BACK_FOR


def test_long_drop_nags_once_and_keeps_waiting(monkeypatch):
    pad, alerts, pauses, _ = run(monkeypatch, down_for=90 * 60)
    assert pauses == []
    assert len(alerts) == 2 and "needs you" in alerts[1]
    assert pad.presses == [bot.Button.B] * bot.CLEAR_MENU_PRESSES


def test_viewer_closed_still_pauses(monkeypatch):
    pad, alerts, pauses, _ = run(monkeypatch, down_for=60, reason="closed")
    assert len(pauses) == 1 and alerts == []
    assert pad.presses == []
