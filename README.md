# Sweet Scent Bot (Pokemon Crystal)

A shiny-hunting bot for **Pokemon Crystal on the 3DS Virtual Console**.
It uses **Sweet Scent** from the field menu to force a wild encounter,
checks whether it's shiny, flees if not, and repeats -- anywhere wild
Pokemon can appear. The character never takes a step, so there's
nothing to drift.

It checks every wild Pokemon, whatever the species, and flees with a RUN-verified
flee (it never presses A in battle unless the cursor is confirmed on RUN).
It also retries before pausing, has a freeze watchdog, and fixes the
console click-freeze. When it finds a shiny it stops and can ping your
phone on Discord.

The bot spots shinies two ways: the shiny animation's "black flash" in
the picture, and the shiny sparkle sound in the game audio. No Pokemon
graphics or game data are included or needed. How each version was
tested is in [CHANGELOG.md](CHANGELOG.md).

> Fan project, not affiliated with or endorsed by Nintendo, Game Freak or
> The Pokemon Company. You need your own legally owned copy of the game.

## What you need

- **A New 3DS or New 2DS** (NTR-HR streaming needs a "New" model) with
  [Luma3DS](https://3ds.hacks.guide/) custom firmware and
  **[NTR-HR](https://github.com/xzn/ntr-hr)** for wireless streaming. The
  [3DS wireless streaming guide](https://wiki.hacks.guide/wiki/3DS:Wireless_streaming)
  covers setting it up.
- **Pokemon Crystal** from the 3DS Virtual Console.
- **A Windows PC** on the same network as the 3DS.
- **Python 3.9 or newer** ([python.org](https://www.python.org/downloads/)).
- **[NTR-VC](https://github.com/Xenon-Hacks/NTR-VC)**, a fork of
  NTRViewer-HR that shares the game picture and audio with the bot.
  Download `NTR-VC-Win-x64.zip` from its
  [Releases](https://github.com/Xenon-Hacks/NTR-VC/releases) page, unzip
  it and run `ntrviewer.exe`. The original NTRViewer-HR won't work.
- Optional: a Discord server of your own, for shiny alerts on your phone.

### 3DS and NTR settings

- **Input Redirection on:** open the Rosalina menu (L + Down + Select) ->
  Miscellaneous options -> Enable InputRedirection. This is how the bot
  presses buttons. The 3DS's IP address is shown on that screen.
- **NTR-HR "No Skip Frame" ON for the top screen:** on the 3DS, X+Y opens
  the NTR-HR menu, then Remote Play > Advanced. Without it NTR-HR only
  sends a frame when the picture changes, and the bot can't tell whether
  it saw the whole shiny flash.
- **NTR-VC's audio on:** in NTR-VC's Debug window, turn on Audio (NTR-HR+).
  The bot reads the audio straight from NTR-VC, so NTR-VC can be muted or
  at any volume. Without audio the bot still works, using the flash check
  alone.

## Setup

1. Download this repository (the green **Code** button -> **Download ZIP**,
   then unzip it, or `git clone` it) and open a terminal in its folder.
2. `py -m pip install -r requirements.txt`
3. Battle Scene in the game's OPTIONS can be ON or OFF; the shiny
   animation plays either way.
4. Start **NTR-VC** (see "What you need") and connect it to the 3DS.
   It can be minimised from here on.
5. Run `py calibrate.py` and follow the prompts: a battle screen, the RUN
   cursor, then the 4 Sweet Scent menu prompts:
   - the whole START menu (cursor on POKEMON),
   - a tight box around the cursor + "POKEMON",
   - press UP once (cursor on POKEDEX) -- no box, it re-captures the same
     spot as the "no arrow" reference,
   - a tight box around the cursor + "SWEET SCENT" in slot 1's menu.
   Any single step can be redone later, e.g. `py calibrate.py --menus`
   (`--battle`, `--cursor`), or everything with `py calibrate.py --all`.
6. Optional, recommended: the Discord alert, below.

### Discord alert

1. **Make a server for it** (you need to own the server to make a
   webhook): in Discord tap **+** at the bottom of the server list ->
   **Create My Own** -> **For me and my friends**.
2. **Create the webhook and copy its link:**
   - *PC:* hover the channel -> gear icon -> **Integrations** ->
     **Webhooks** -> **New Webhook** -> **Copy Webhook URL**.
   - *Phone:* tap the server name -> **Settings** -> **Integrations** ->
     **Webhooks** -> **New Webhook** -> tap it -> **Copy Webhook URL**.

   The link looks like `https://discord.com/api/webhooks/123.../AbC...`.
   Keep it private: anyone with it can post in your channel.
3. **Save it:**
   ```
   py alarm.py --setup
   ```
   Paste the link (right-click) and press ENTER. It's saved to
   `config.json` (never uploaded to GitHub, and kept when you re-run
   `calibrate.py`) and a test alert is sent.
4. **Check your phone got it.** If not: Discord doesn't push to your phone
   while you're active in Discord on the PC (close it or wait a few
   minutes), and check notifications are allowed for Discord in the
   phone's settings.

`py alarm.py --test` sends another test any time. To turn the @everyone
ping off, add `"discord_ping_everyone": false` to `config.json`. The bot
says at startup whether the alert is on.

## Party setup (important)

Battle Scene can be ON or OFF: the shiny animation plays either way (see v25 in
[CHANGELOG.md](CHANGELOG.md)).

**Party slot 1 must know Sweet Scent AND be faster than the fastest wild
Pokemon where you're using it.** In Gen II a faster Pokemon always
escapes; a slower one can fail, and the flee logic assumes escape always
succeeds.

## Close InputRedirectionClient-Qt first (important)

Don't run InputRedirectionClient-Qt (or any other input tool connected to
the 3DS) while the bot runs. The bot sends its own inputs; a second
program sending "no buttons pressed" at the same time can make a single
bot press arrive twice, or not at all.

## Where it works

Anywhere Sweet Scent can find a wild Pokemon. Per Crystal's own code
(pret/pokecrystal): on grass tiles, on water while surfing, and anywhere
inside caves and dungeons except on ice -- in an area that has wild
Pokemon at the current time of day. Stand on such a tile before starting.
(In a pitch-dark cave without Flash the bot may fall back to its slower
checks, since the overworld is too dark to tell from a screen fade.)

## Running it

```
py sweet_scent_bot.py --ip <3DS IP>
```

Replace `<3DS IP>` with your own 3DS's IP address, the same one you
enter in NTR-VC to connect (your router's list of connected devices
shows it too).

Start on the overworld, on a tile where wild Pokemon appear, with no
menu open. Each Sweet
Scent attempt prints its checks, e.g.
`start menu open: 0.93/0.94 [OK]`. The first number is the first look,
the second is the confirming look; both must reach 0.75. If a check
keeps failing with scores just under 0.75, redo that box with
`py calibrate.py --menus`.

`py test_flee.py --ip ...` still works for testing a single flee.

## How the menu path works

1. B, wait, START -- B first because START toggles the menu; this makes
   sure it's never pressed while the menu is already open.
2. Check the START menu is open, then move the cursor to POKEMON if
   needed: the bot finds which row the arrow is on (using the arrow shape
   from your two POKEMON calibration pictures) and presses DOWN if it's
   above POKEMON or UP if it's below -- always the short way, checking a
   screenshot after every press. The check compares
   two references -- arrow on POKEMON vs. arrow on POKEDEX -- because the
   POKEMON text alone can look like a match when the arrow is elsewhere. Direction buttons
   are only sent once the menu is confirmed open, so they can never
   walk the character.
3. A on POKEMON, then **confirm it worked** (the START menu must be gone).
   If the menu is still there with the cursor still on POKEMON, the press
   didn't land, so it presses A again (up to 3 times). Then A on the first
   Pokemon -- no checks, no cursor movement in the party screen, by design.
4. Look (never move) to confirm SWEET SCENT is under the cursor, then A.
   If it isn't there, back out with B instead of guessing.
5. "<POKEMON> used SWEET SCENT!" waits for a button, so press B every
   second (harmless everywhere here) until the battle starts, up to 15 s.

If any step fails, it backs out with B only (safe everywhere) and tries
again. After 3 failures in a row it pauses and waits for you.

## Speed (fast mode)

After the first encounter, the bot switches to a fast mode that watches
the stream ~20 times a second and reacts as soon as the next screen
appears, instead of waiting on fixed timers. It only reacts to a screen
seen AFTER its own button press, so a stale frame can never trigger an
action.

Tuned from real recordings and test_menu_input.py measurements:
- "Confirmed" means true on every look for 0.2 s -- longer than the
  fastest double cursor move seen (0.1 s), so a cursor passing THROUGH
  an item can't count as stopping on it.
- On the START menu about 1 in 5 presses is lost outright (never late:
  every press that landed showed up within 0.45 s). Lost presses are
  retried after 1.0 s. A background keepalive made no difference.
- Presses are held 0.2 s: 0.1 s lost half of them, and 0.25 s+ holds
  sometimes made the menu auto-repeat (cursor moved two rows).
- START pressed while the overworld was still fading in was ignored, so
  it waits until the overworld has been still for 0.5 s. "Is this a real
  screen or a fade?" is measured on a central patch of the picture,
  because NTR Viewer's black side bars made a flat fade look detailed.

In simulation: ~21 s per encounter with no lost presses (the human
recording: ~18-20 s; v4: ~46 s). Faster streams or fewer late presses
bring it down further.

Battle safety in fast mode: "Wild X appeared!" gets up to 3 A presses,
all within 2 s -- the menu always needs ~4.2 s after that text clears, so
none can reach it, even if one arrives ~1 s late. DOWN/RIGHT are only
sent while the battle menu is on screen, and the confirming A only after
RUN has held for 0.35 s. Anything unclear falls back to the slower, fully
checked routines.

## How encounters are checked

A background thread records every new NTR-VC frame from the moment each
Sweet Scent attempt starts. Once the wild Pokemon is fully displayed
("Wild X appeared!" is in the text box -- the game prints it only after
the sprite has slid in and after the shiny animation -- and has finished
printing), the bot looks back over the frames since the battle
transition went black, for a short burst of photo-negative frames between
two normal battle screens:

- found: **shiny** -- it stops, saves a screenshot to alerts/, and waits
  for you;
- not found, and the frames came in close enough together that a flash
  couldn't have been missed: **normal** -- it flees;
- anything else (frames more than 75 ms apart, the start of the battle
  not recorded, a battle screen that doesn't look like a battle intro):
  **can't tell** -- it stops and saves a screenshot, the same as for a
  possible shiny. If it's normal, run from it yourself and press ENTER.

It waits for the connection quality to be at least 50% before looking.
Nothing needs calibrating for this and no sprites are involved: the same
check works for every species.

If the bot finds itself already in a battle it didn't see start (e.g. a
Sweet Scent attempt gave up just as the encounter began), it checks the
frames it recorded during that attempt; if the start of the battle isn't
among them, it says it can't tell and stops.

## NTR-VC (the frame-sharing viewer)

The bot reads the game picture straight from
[NTR-VC](https://github.com/Xenon-Hacks/NTR-VC), a fork of NTRViewer-HR
that publishes every decoded frame (and the game audio) to shared
memory. That is the only way the bot gets its picture, so NTR-VC
can be **minimised, covered or moved anywhere** while the bot runs, and
nothing needs re-boxing if the window moves. Button presses are
unaffected: the bot sends them to the 3DS directly.

If the picture looks wrong, `py test_shared_frame.py` checks the
connection and saves shared_frame_test.png. The game should be upright,
with black bars left and right. If it's sideways or upside down, try
`--rotation 0`, `2` or `3`, and put the one that works in config.json as
`"shared_rotation": N`.

The bot's first line says `Reading frames from NTR-VC (it can be
minimised)...`. If NTR-VC isn't running or connected, it says so and
stops.

## Log files

Everything the bot prints is also saved to logs/sweet_scent_<date>_<time>.txt,
with the date and time at the start of each line. So you always have the
full history of a run (and when something happened), even if the console
can't be copied or gets closed.

To copy text from the console WHILE the bot runs: click-to-select is
turned off on purpose (a stray click used to freeze the bot), so
right-click the window's title bar -> Edit -> Mark. That pauses the bot
until you press Enter.

## If the 3DS, NTR Viewer or NTR-VC freezes

NTR Viewer keeps showing the last picture it received, so a frozen setup
can look normal. Before every button press the bot checks that the picture
can be trusted. It can't if:

- NTR Viewer reports 0% connection quality (a dip, or the 3DS froze);
- Windows reports NTR Viewer / NTR-VC as "Not Responding" (works even while
  it's minimised -- a frozen window's title would otherwise keep showing
  its last, healthy-looking connection quality);
- NTR Viewer / NTR-VC was closed after the bot saw it running;
- with the frame-sharing NTR-VC: its heartbeat (a connection-quality update
  about once a second) stops for 10 s while its window isn't minimised.

While any of these holds, the bot presses NOTHING and just waits. If it
clears by itself, the bot carries on and logs one line saying how long it
lasted. If it lasts 30 seconds straight:

- 0% connection quality (the 3DS stopped streaming): the bot keeps waiting
  for NTR-VC to reconnect, then backs out of any menu with B and carries
  on by itself (see v24 in [CHANGELOG.md](CHANGELOG.md)).
- Anything else: the bot pauses, with a message saying which of these it
  was. Get everything running and streaming again, go to the overworld
  with no menu open, and press ENTER.

If a battle is already on screen when a cycle starts (for example after
such a pause), the bot flees it first, using the original fully checked
flee.

## Debug screenshots

Every Sweet Scent attempt saves a picture of each step into its own
timestamped folder inside `debug_sweet_scent/` (the last 10 attempts are
kept).
If it fails, the terminal says so, and those pictures show exactly what
the 3DS was showing at each step. If you report a problem, attach
them along with the log.

## Tuning

`MENU_SETTLE` in `sweet_scent.py` (1.5 s) is how long it waits after each
menu press before looking. It's set for a stream running as slow as
1-3 FPS. If your stream holds ~10 FPS, you can try 1.0 to speed things
up; if checks start failing, put it back.

## If the bot ever freezes

The watchdog writes `hang_report.txt` if the bot makes no progress for 3
minutes (it stays quiet while a deliberate pause is waiting for ENTER).
If you report a problem, attach that file and a screenshot.

The bot disables the Windows console's click-to-select freeze for its
window at startup. To copy text while it runs, right-click and choose
Mark/Select -- that pauses it, so press Enter when you're done.

## Windows: `python` command acting weird?

Use `py` instead of `python` for every command. `py` is the Python
launcher that the python.org installer adds, and it always runs the
Python you installed.

## Running the tests

The tests use simulated battles, so no 3DS, game or graphics are needed:

```
py -m pip install -r requirements-dev.txt
py -m pytest tests
```

## License

MIT, see [LICENSE](LICENSE). `luma_input.py` is an independent
re-implementation of Luma3DS's Input Redirection protocol; credit to
TuxSH, Stary2001 and hlixed (TPPFLUSH) for documenting it.
