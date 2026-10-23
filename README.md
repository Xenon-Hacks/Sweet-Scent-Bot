# Sweet Scent Bot (Pokemon Crystal)

Uses **Sweet Scent** from the field menu to force a wild encounter, checks
whether it's shiny, flees if not, and repeats -- anywhere wild Pokemon can
appear. The character never takes a step, so there's nothing to drift.

It checks every wild Pokemon, whatever the species, and flees with a RUN-verified
flee (it never presses A in battle unless the cursor is confirmed on RUN).
It also retries before pausing, has a freeze watchdog, and fixes the
console click-freeze.

## What's new in v26: sound check retuned on the real 3DS

- **Tested on a real forced 3DS**: the flash check caught 35 of 35, with No Skip
  Frame on and off (correlation -0.99 to -1.00, all 5 inverted frames).
- **The sound check scored them far lower than the emulator did:** 0.12-0.23,
  so the old 0.20 line missed 21 of 35. Over NTR-VC's shared audio,
  ~50,000 normal encounters never scored above 0.09. The bot now calls
  0.11+ shiny and under 0.10 normal (`SHINE_SHINY`, `SHINE_NORMAL` in
  `sweet_scent_bot.py`).
- With `--loopback` (the PC-speaker path) normals have reached 0.13, so
  that path may now stop for normal encounters.

## What's new in v25: the flash check now sees a real shiny

- **Tested against the real game's shiny animation.** The game was built
  from the pokecrystal decompile, run in an emulator, and made to start
  wild battles with 9 species, each shiny and normal (no game graphics
  are kept anywhere).
- **The flash check missed every real shiny over NTR-VC, and that's
  fixed.** On the Game Boy Color the shiny flash only blacks out the
  battle field: the Pokemon keep their colours and the empty text box
  stays white. The old photo-negative test counted the text box too and
  scored the real flash at about -0.2 over NTR-VC-like frames, short of
  its -0.3 line, so it said "normal". It now looks at the battle field
  only (about -1.0). Result: 9 of 9 shinies flagged and 9 of 9 normals
  passed, at 1x and 1.5x game size and at every frame rate down to one
  frame in five.
- `frame_recorder.py` no longer lets a small bright patch on the flash
  frame (the text box, a sprite) move where it thinks the game is.
- **The sound check already worked:** the real shinies scored 0.38-0.39
  (0.34-0.36 with added hiss) against 0.06-0.13 for normal ones, well
  past the 0.20 shiny line. With the bot's sound on, v24 would still
  have stopped for these shinies.
- **Battle Scene doesn't matter after all.** With it OFF the game only
  skips move animations; the shiny animation still plays (checked in the
  game and in its code), so the flash and sound are both there.
- The simulated tests now draw the flash the way the Game Boy Color does;
  the old check fails them, the new one passes.

## What's new in v24: a dropped stream no longer stops the bot

- **When the 3DS stops streaming (Connection Quality 0%), the bot waits
  and carries on by itself** instead of pausing until you press ENTER.
  NTR-VC keeps reconnecting on its own; in a real log the 3DS came back
  after 11 minutes, while the bot had stopped after 30 seconds.
- It still presses nothing while the picture is gone. Once the picture
  has been back for 5 s it presses B a few times to back out of any menu
  it was in, then starts a fresh cycle (a battle on screen gets the fully
  checked flee).
- Discord: one 📡 **Stream dropped.** message when it starts waiting, and
  a ⚠️ **Bot paused, it needs you.** one if there's still no picture after
  20 minutes (it keeps waiting either way).
- NTR-VC closing, freezing or going Not Responding still pauses for ENTER
  as before, since only you can fix that.
- `tests/test_stream_drop.py` covers the short drop, the long drop and the
  closed viewer.

## What's new in v23: Discord alert on your phone

- **When the bot stops, it can ping your phone on Discord**, ported from
  the Suicune bot (`alarm.py`). It posts as "Sweet Scent Bot":

  > ✨ **Shiny found!**
  > shiny flash: 3 inverted frame(s), ...
  > Encounter #1,284 · 9h 12m of runtime
  > Bot is paused, waiting for you.
  > @everyone
  > *(the battle screenshot)*

  A "couldn't tell" encounter sends ❓ **Possible shiny!** with the
  reason and screenshot. The other pauses (NTR-VC or the 3DS dead for 30 s,
  Sweet Scent failing 3 times, a battle stuck for ~6 minutes) send
  ⚠️ **Bot paused, it needs you.** with what went wrong.
- The upload runs in the background and a failed one is only printed, so
  it never delays or stops the pause. With no webhook set up the bot works
  exactly as in v22.
- Set it up with `py alarm.py --setup` (see "Discord alert" under Setup).
  A webhook link from the Suicune bot works here too.
- `tests/test_alarm.py` sends alerts to a stand-in webhook and checks the
  text, the screenshot, the @everyone switch, and that a dead webhook
  never raises.

## What's new in v22: game audio straight from NTR-VC

- **The sound check no longer depends on the PC's volume or output
  device.** NTR-VC 2.2.0 and later share the 3DS game audio through
  shared memory, the same way they share the picture, and the bot reads
  it there (`shared_audio.py`). NTR-VC can be muted, at 0 or on any
  output, and other programs' sound is never mixed in. The only setting
  left is NTR-VC's audio on (its Debug window: Audio (NTR-HR+)).
- With an older NTR-VC the bot says so and listens to the PC's speakers
  as in v21 (`--audio-device` still applies there). `--loopback` forces
  the speakers even with a new NTR-VC.
- `tests/test_shared_audio.py` checks the reader against a stand-in for
  the viewer: audio arrives whole and in order across the ring's end,
  after falling behind, and after a viewer restart, and the shiny sound
  sent through it is still found.

## What's new in v21: the bot also listens for the shiny sound

- **Shinies are also spotted by their sound.** The shiny animation plays
  SFX_SHINE eight times (pokecrystal: `data/moves/animations.asm`,
  `BattleAnim_SendOutMon.Shiny`; `audio/sfx.asm`, `Sfx_Shine_Ch5`): a
  square wave stepping 512, 683, 1024, 2048 and 4096 Hz, one game frame
  each, restarted every 5 frames, about 0.8 s in all. `shine_sound.py`
  slides a spectrogram of that exact sound along the game audio
  (`audio_recorder.py` records the PC's speakers). Nothing else in a
  wild battle sounds like it.
- **Either check finding a shiny stops the bot.** A clear "no shiny
  sound" also settles an encounter whose picture had a gap, so Wi-Fi
  hiccups no longer stop the bot with COULDN'T TELL. With no audio it
  falls back to the flash alone, as in v20; `--no-sound` turns the sound
  check off.
- Measured on a real 3DS over NTR-VC: normal encounters scored 0.06-0.13;
  the shiny sound mixed into that real audio scored 0.30-0.47 (0.30+
  even with a 120 ms dropout); the game's real shiny animation, recorded
  in a Game Boy emulator, scored 0.36. The bot calls 0.20+ shiny and
  under 0.15 normal. Not yet seen: a real shiny on the 3DS.

**Two NTR settings this needs:**

- **NTR-HR "No Skip Frame" ON for the top screen** (on the 3DS, X+Y opens
  the NTR-HR menu, then Remote Play > Advanced). Without it NTR-HR only
  sends a frame when the picture changes, and the flash check sees 500 ms
  gaps on every encounter.
- **NTR-VC's audio on** (its Debug window: Audio (NTR-HR+)). With
  NTR-VC 2.2.0 or later that's all (see v22). With an older one the bot
  records what Windows plays after each app's volume, so NTR-VC at 0 or
  muted is silence to it. To hunt without hearing the game: in Settings >
  Sound > Volume mixer, set NTR-VC's output device to one nobody listens
  to, such as "Speakers (Steam Streaming Speakers)", keep NTR-VC's volume
  at 100, and run `py sweet_scent_bot.py --ip <3DS IP> --audio-device
  "Steam Streaming"`. Without `--audio-device` it listens to the default
  speakers, and hears everything else playing there too.

## What's new in v20: no Pokemon sprites anywhere

- **Shinies are spotted by their animation, not their colours** (ported
  from the Static Encounter bot V2). When a wild Pokemon is shiny, Crystal
  plays the shiny animation before "Wild X appeared!": the whole battle
  screen flashes to a photo-negative for 5 frames (the "black flash"),
  then sparkles circle it. A normal one gets no animation at all. The bot
  watches for that flash (`shiny_flash.py`), which works the same for
  every species. The `NORMAL/` and `SHINY/` sprite folders and
  `sprite_id.py` are gone, and nothing in this build contains any Pokemon
  graphics.
- **Battle Scene must be ON** in the game's OPTIONS. With it off the game
  skips battle animations, the shiny one included. (Not so: see v25.)
- Frames are recorded non-stop on a background thread
  (`frame_recorder.py`), so the ~83 ms flash can't slip by while the bot
  is pressing buttons. Only new NTR-VC frames are recorded, so the bot
  knows the real gap between stream frames.
- If NTR-VC's frames came in more than 75 ms apart while the battle
  started, a flash could have fallen between two of them; the bot then
  stops and asks you ("COULDN'T TELL") rather than flee a possible shiny.
- What it no longer does: name the species, or stop on unrecognised
  Pokemon such as Unown (an Unown is checked like everything else).
- `tests/` checks the flash detector against simulated battle starts,
  including NTR-VC's frame layout (no 3DS, ROM or graphics needed):
  `py -m pytest tests`.

Two fixes on top of the Static Encounter bot's code, both found by the
NTR-VC-layout test: the flash frames are mostly black, so finding the
game inside the 3DS top screen failed on exactly those frames and the
flash stopped looking like a photo-negative (a missed shiny); the
recorder now keeps the game's position from the last bright frame. And
the recorder takes each frame's number from the frame it actually read,
so a frame arriving between two reads is no longer skipped.

How the flash was pinned down, in the pokecrystal decompile
(github.com/pret/pokecrystal): `BattleStartMessage` in
`engine/battle/core.asm` plays `ANIM_SEND_OUT_MON` only when
`BattleCheckEnemyShininess` says shiny; its `.Shiny` branch in
`data/moves/animations.asm` starts with `BATTLE_BG_EFFECT_FLASH_INVERTED`,
which (`engine/battle_anims/bg_effects.asm`) reverses the background
palette for 5 frames. The 3DS Virtual Console's anti-flashing patch only
touches a few move animations, not this one.

## Where it works

Anywhere Sweet Scent can find a wild Pokemon. Per Crystal's own code
(pret/pokecrystal): on grass tiles, on water while surfing, and anywhere
inside caves and dungeons except on ice -- in an area that has wild
Pokemon at the current time of day. Stand on such a tile before starting.
(In a pitch-dark cave without Flash the bot may fall back to its slower
checks, since the overworld is too dark to tell from a screen fade.)

## Close InputRedirectionClient-Qt first (important)

Don't run InputRedirectionClient-Qt (or any other input tool connected to
the 3DS) while the bot runs. The bot sends its own inputs; a second
program sending "no buttons pressed" at the same time can make a single
bot press arrive twice, or not at all.

## Party setup (important)

Battle Scene can be ON or OFF: the shiny animation plays either way (v25).

**Party slot 1 must know Sweet Scent AND be faster than the fastest wild
Pokemon where you're using it.** In Gen II a faster Pokemon always
escapes; a slower one can fail, and the flee logic assumes escape always
succeeds.

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

## Setup

1. `py -m pip install -r requirements.txt`
2. Battle Scene in the game's OPTIONS can be ON or OFF; the shiny
   animation plays either way.
3. Start **NTR-VC** (the frame-sharing NTRViewer-HR, see below) and connect
   it to the 3DS. It can be minimised from here on.
4. Run `py calibrate.py` and follow the prompts: a battle screen, the RUN
   cursor, then the 4 Sweet Scent menu prompts:
   - the whole START menu (cursor on POKEMON),
   - a tight box around the cursor + "POKEMON",
   - press UP once (cursor on POKEDEX) -- no box, it re-captures the same
     spot as the "no arrow" reference,
   - a tight box around the cursor + "SWEET SCENT" in slot 1's menu.
   Any single step can be redone later, e.g. `py calibrate.py --menus`
   (`--battle`, `--cursor`), or everything with `py calibrate.py --all`.
   A `config.json` left over from the old screen-capture setup is
   detected and replaced automatically.
5. Optional, recommended: the Discord alert, below.

### Discord alert

1. **Make a server for it** (you need to own the server to make a
   webhook): in Discord tap **+** at the bottom of the server list ->
   **Create My Own** -> **For me and my friends**. (Already did this for
   the Suicune bot? Reuse that webhook link and skip to step 3.)
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

The bot reads the game picture straight from NTR-VC, a small fork of
NTRViewer-HR (ntrviewer-hr-frame-share.zip -- see its
FRAME_SHARE_README.md for building it) that publishes every decoded frame
to shared memory. That is the only way the bot gets its picture, so NTR-VC
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
  on by itself (see v24 above).
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
the 3DS was showing at each step. Send them along with the log.

## Tuning

`MENU_SETTLE` in `sweet_scent.py` (1.5 s) is how long it waits after each
menu press before looking. It's set for a stream running as slow as
1-3 FPS. If your stream holds ~10 FPS, you can try 1.0 to speed things
up; if checks start failing, put it back.

## If the bot ever freezes

The watchdog writes `hang_report.txt` if the bot makes no progress for 3
minutes (it stays quiet while a deliberate pause is waiting for ENTER).
Send that file along with a screenshot.

The bot disables the Windows console's click-to-select freeze for its
window at startup. To copy text while it runs, right-click and choose
Mark/Select -- that pauses it, so press Enter when you're done.

## Windows: `python` command acting weird?

Use `py` instead of `python` for every command (see the master README).
