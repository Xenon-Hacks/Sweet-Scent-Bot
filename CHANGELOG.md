# Changelog

Older notes on how each version was built and tested. For setup and
use, see [README.md](README.md).

## v26: sound check retuned on the real 3DS

- **Tested on a real forced 3DS**: the flash check caught 35 of 35, with No Skip
  Frame on and off (correlation -0.99 to -1.00, all 5 inverted frames).
- **The sound check scored them far lower than the emulator did:** 0.12-0.23,
  so the old 0.20 line missed 21 of 35. Over NTR-VC's shared audio,
  ~50,000 normal encounters never scored above 0.09. The bot now calls
  0.11+ shiny and under 0.10 normal (`SHINE_SHINY`, `SHINE_NORMAL` in
  `sweet_scent_bot.py`).
- With `--loopback` (the PC-speaker path) normals have reached 0.13, so
  that path may now stop for normal encounters.

## v25: the flash check now sees a real shiny

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

## v24: a dropped stream no longer stops the bot

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

## v23: Discord alert on your phone

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

## v22: game audio straight from NTR-VC

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

## v21: the bot also listens for the shiny sound

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

## v20: no Pokemon sprites anywhere

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

