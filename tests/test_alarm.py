"""The Discord alert against a stand-in webhook on localhost: the message
and screenshot arrive as Discord expects them, the @everyone ping can be
turned off, and a dead webhook never raises (the bot must still pause)."""

import http.server
import json
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import alarm  # noqa: E402

received = []


class Webhook(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        received.append((self.headers["Content-Type"], body))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


def payload(body):
    start = body.index(b"\r\n\r\n", body.index(b'name="payload_json"')) + 4
    return json.loads(body[start:body.index(b"\r\n--", start)])


def test_alarm():
    server = http.server.HTTPServer(("127.0.0.1", 0), Webhook)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/api/webhooks/1/x"

    text = alarm.format_alert("shiny", 1284, 9 * 3600 + 12 * 60)
    assert text.splitlines() == ["✨ **Shiny found!**",
                                 "Encounter #1,284 · 9h 12m of runtime",
                                 "Bot is paused, waiting for you."], text
    unsure = alarm.format_alert("unsure", 3, 125, "too few frames")
    assert "couldn't tell" in unsure and "too few frames" in unsure
    assert "· 2m of runtime" in unsure
    assert "needs you" in alarm.format_alert("paused", 0, 0, "NTR-VC closed")

    picture = os.path.join(tempfile.mkdtemp(), "shot.png")
    with open(picture, "wb") as f:
        f.write(b"\x89PNG fake")
    alarm.notify({"discord_webhook_url": url}, text, picture)(5)
    ctype, body = received.pop()
    assert ctype.startswith("multipart/form-data; boundary=")
    p = payload(body)
    assert p["username"] == "Sweet Scent Bot"
    assert p["content"] == text + "\n@everyone"
    assert p["allowed_mentions"] == {"parse": ["everyone"]}
    assert b'filename="shot.png"' in body and b"\x89PNG fake" in body

    alarm.notify({"discord_webhook_url": url, "discord_ping_everyone": False},
                 text, None)(5)
    p = payload(received.pop()[1])
    assert p["content"] == text and p["allowed_mentions"] == {"parse": []}

    # No webhook set up: nothing sent. Dead webhook: printed, never raised.
    alarm.notify({}, text)(5)
    server.shutdown()
    server.server_close()
    alarm.notify({"discord_webhook_url": url}, text, picture)(5)
    assert not received
    print("alarm OK")


if __name__ == "__main__":
    test_alarm()
