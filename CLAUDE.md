# CLAUDE.md

One-knob Ableton Live Session view controller: Teensy 4.1, PEC11R rotary encoder with push switch, 1.3" 128x64 I2C OLED. Knob scrolls scenes (clockwise = down), click launches, the OLED shows the selected scene's number, name, tempo and time signature.

- `firmware/navigator_t2/navigator_t2.ino` — device sketch
- `remote-script/NavigatorT2/` — Live MIDI Remote Script (Python)
- `tools/test_t2.py` — host-side check of the SysEx encoder

## Commands

    python3 tools/test_t2.py        # prints PASS; stdlib only, no Live needed

    arduino-cli compile --fqbn teensy:avr:teensy41:usb=midi firmware/navigator_t2
    arduino-cli upload  --fqbn teensy:avr:teensy41:usb=midi -p usb:<id> firmware/navigator_t2

`<id>` comes from `arduino-cli board list` (Teensy row, e.g. `usb:2110000`); plain `-p usb` fails. USB type must be `usb=midi` or `usbMIDI` does not exist. Libraries: `Encoder`, `U8g2`.

The Remote Script imports `Live` and `_Framework`, so it only runs inside Ableton. Before changing it, invoke the `ableton-lom-skill-main` skill rather than recalling LOM names from memory.

## Install the Remote Script

Live runs a copy, not the project files. After any edit, re-copy and restart Live:

    rsync -a --exclude __pycache__ remote-script/NavigatorT2 "$HOME/Music/Ableton/User Library/Remote Scripts/"

In Live: Preferences > Link, Tempo & MIDI > Control Surface = `NavigatorT2`, Input and Output = `Teensy MIDI`. Don't unplug the Teensy while Live is open; if the display sticks on "waiting for Live", toggle Output to None and back.

## Architecture

Two-way MIDI over USB; the Remote Script decides what the display shows.

```
knob turn  -> CC 20, ch1, two's-complement relative (1..63 = +, 65..127 = -)  -> _on_scroll  -> moves song.view.selected_scene (clamped, no wrap)
knob press -> Note 60 ch1 on/off                                               -> _on_fire    -> selected_scene.fire() on note-on
Live       -> SysEx F0 7D 02 <num:2><playing:1><tempo:2><phase:2><stempo:2><sig:2><name:20><prog:1><left:2><total:2> F7  (40 bytes) -> firmware stores num, flag, tempo, phase, scene tempo, sig, name, progress and redraws
```

Defined in two places; change both or neither:
- CC number, note number, channel: `CC_SCENE_SCROLL` / `NOTE_SCENE_FIRE` in `NavigatorT2.py` and `navigator_t2.ino`.
- SysEx format: `protocol.py` (encoder: `NAME_LEN = 20`, manufacturer ID `0x7D`, type `0x02`) and `onSysEx()` in the `.ino` (decoder: length `14 + NAME_LEN + 5 + 1`, header bytes). `test_t2.py` asserts the 40-byte length. Keep `protocol.py` free of `Live` imports so the test can load it.

`num` is the 1-based selected scene as two 7-bit bytes (hi, lo). `playing` is 1 when any track's `playing_slot_index` equals the selected scene, 2 when the scene is empty (`Scene.is_empty`, polled, not observable), else 0; while it is 0 the firmware blinks all three text rows, one on/off cycle per beat. At 2 the rows stay steady and only the middle row alternates, on the stopped-screen cycle (1 s name, 1 s message, `STOP_SCENE_MS` / `STOP_MSG_MS`, not the beat), the name with `<no clips>` (`EMPTY_MSG`, centered in `u8g2_font_fub14_tr`, never scrolls); an empty scene is shown this way as soon as it is selected, since a launch is indistinguishable from a selection (`tempo` is BPM x 10 as hi, lo). `phase` is `current_song_time` mod 1 x 16383 (hi, lo; `0x3FFF` = transport stopped): each message re-anchors the blink so it flashes on Live's beat, and the firmware free-runs between messages. `BLINK_LATENCY_MS` in the `.ino` shifts the blink later to match audio output latency. `stempo` (BPM x 10, hi, lo) and `sig` (numerator, denominator) are the selected scene's own tempo / time signature, or the song's when the scene has none; they fill the bottom row.

`prog` / `left` / `total` drive the progress bar behind the middle row. The script (`_progress`) picks the row holding the most playing clips (ties topmost, as in ableton-navigator-ts), then its longest playing clip, whatever scene is selected. `prog` is 0 none, 1 looping, 2 one-shot, 3 finished; `left` / `total` are tenths of a second to the end of this pass and per full pass (`clip_progress` in `protocol.py`). A looping clip is measured from its Start marker, `(playing_position - start_marker) mod length`, so the bar is empty at the Start marker on every pass and full just before the playhead returns to it; the jump back to Loop start falls part-way across. A one-shot runs from its start to its end. The firmware anchors a free-running timer on each message (`progStart`) and fills a box over the band between the rules, drawing the name in XOR so it inverts over the fill; a loop wraps by modulo, a one-shot clamps full. The script resends at once when the playhead drifts more than `PROGRESS_DRIFT_S` from where that free-run says it should be (relaunch, jump, tempo change), otherwise on the ~2 s resend. When nothing plays and the last one-shot was within `FINISHED_LEFT_S` of its end, the script sends 3 until another clip starts and the band flashes full 1 s on / 1 s off (a long one-shot ending falls back to a shorter looping clip). Hidden while the transport is stopped.

Names are ASCII-only (non-ASCII becomes `?`), padded to 20. Unnamed scenes are sent as their 1-based number, since the LOM reports an empty name.

A scene selection change is sent immediately from its listener. Everything else is dirty-flag driven: scene-list changes, playing state, tempo and transport set `_dirty`, and `update_display()` (Live's ~100 ms tick) sends only when dirty. It also resends every `RESEND_TICKS` (20, about 2 s) so a device connected after Live catches up; there is no handshake message.

While the transport is stopped (`phase` = `0x3FFF`) the blink is off and the display alternates the steady scene screen with a "Live stopped. / Push play." screen (`STOP_MSG_MS` / `STOP_SCENE_MS`); the stop itself starts on the message, and each scene change restarts the cycle so the scene shows for `STOP_SETTLE_MS` before the message returns. If no SysEx arrives for `LIVE_TIMEOUT_MS` (Live resends about every 2 s) the firmware drops back to "waiting for Live".

The middle row uses `u8g2_font_fub20_tr`, the largest font that fits the 28 px band between the rules (cap height 20, ascent + descent 25). A name wider than `NAME_FIT` (124 px, roughly 9-10 characters) holds for `SCROLL_DELAY_MS` and then scrolls left in a loop with `SCROLL_GAP` between repeats; the scroll restarts only when the scene number or name changes, not on the periodic resend. I2C runs at the SH1106 default of 400 kHz (U8g2 `i2c_bus_clock_100kHz = 4`), so no `setBusClock` call is needed.

Firmware `loop()` is one pass: drain up to 64 `usbMIDI.read()` events (each call consumes one 3-byte event and a SysEx is 12, so a single call per pass lags once redraws block), set blink/scroll redraws, one `draw()` if `needDraw` (`onSysEx` only sets the flag), encoder, then button (20 ms debounce). `draw()` blocks for a full I2C frame. Encoder counts are divided by `COUNTS_PER_DETENT` and the remainder is written back so partial detents are kept. Contact bounce can leave the count off by a fraction of a click, which makes the first click after a reversal not fire; so when the count has been still for 20 ms and A and B are both high (the detent level, measured), the count is snapped to the nearest multiple of `COUNTS_PER_DETENT`.

## Hardware

- Encoder A / B = pins 2 / 3, common to GND; switch = pin 4 to GND. Internal pull-ups, no external resistors. Swapping A and B reverses direction.
- OLED on 3.3 V, SDA = pin 18, SCL = pin 19. Constructor is `U8G2_SH1106_128X64_NONAME_F_HW_I2C`; an SSD1306 module needs `U8G2_SSD1306_128X64_NONAME_F_HW_I2C`.
- Encoder is Bourns PEC11R-4220F-S0024 (datasheet Rev. 04/26): 24 detents and 24 pulses per turn, so `COUNTS_PER_DETENT = 4`. Datasheet contact bounce is 2.0 ms max at 15 RPM *with* Bourns' RC filter (10k + 0.01 µF per channel); this build has no hardware filter, hence the rest resync in `loop()`.

## Gotchas

- `onSysEx()` calls `beatMs()` before its definition; this works because the Arduino preprocessor generates prototypes. Keep it a single `.ino` in its folder.
- `_on_scroll` and `_snapshot` (used by `update_display` and the selection listener) call `scenes.index(selected_scene)`, which raises if the selected scene is not in the list. Not guarded.
