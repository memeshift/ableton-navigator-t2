import importlib.util, pathlib
p = pathlib.Path(__file__).parent.parent / "remote-script/NavigatorT2/protocol.py"
s = importlib.util.spec_from_file_location("protocol", p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)

msg = m.scene_message("Intro", 0)
assert len(msg) == 14 + 20 + 5 + 3 + 20 + 1 and msg[0] == 0xF0 and msg[-1] == 0xF7 and msg[1:3] == (0x7D, 2)
assert len(msg) == 63   # firmware onSysEx() checks 14 + NAME_LEN + 5 + 3 + NAME_LEN + 1
assert all(b < 0x80 for b in msg[1:-1])
assert bytes(msg[14:34]).decode().rstrip() == "Intro"
assert bytes(m.name_bytes("Café ☃" * 5)).decode().count("?") > 0 and len(m.name_bytes("x" * 99)) == 20
assert msg[3:8] == (0, 1, 0, 9, 48) and m.scene_message("x", 150, True, 128.5)[3:8] == (1, 23, 1, 10, 5)   # num 1 / 151, playing flag, 120.0 / 128.5 BPM
assert msg[8:10] == (127, 127) and m.scene_message("x", 0, False, 120, 2.25)[8:10] == (31, 127)   # no beat -> 0x3FFF; beat 2.25 -> phase 4095
assert m.scene_message("x", 0, False, 120, 7.0)[8:10] == (0, 0) and m.scene_message("x", 0, False, 120, 0.99999)[8:10] != (127, 127)
assert msg[10:14] == (9, 48, 4, 4) and m.scene_message("x", 0, False, 120, None, 128.5, (7, 8))[10:14] == (10, 5, 7, 8)   # 120.0 4/4 default; 128.5 7/8
assert m.scene_message("x", 0, 2)[5] == 2 and m.scene_message("x", 0, True)[5] == 1 and m.scene_message("x", 0, 0)[5] == 0   # playing byte: 0 / 1 / 2 = empty scene
assert msg[34:39] == (0,) * 5 and m.scene_message("x", 0, 1, progress=(2, 12.3, 30))[34:39] == (2, 0, 123, 2, 44)   # state, left 123, total 300 tenths
assert msg[39:42] == (0, 0, 0) and bytes(msg[42:62]).decode().strip() == ""   # no track: num 0, kind 0, blank name
t = m.scene_message("x", 0, track=("Bass", 4, 3))
assert t[39:42] == (0, 5, 3) and bytes(t[42:62]).decode().rstrip() == "Bass" and len(t) == 63   # track 5, folded group
assert m.scene_message("x", 0, track=("g", 149, 2))[39:42] == (1, 22, 2)   # track 150, open group
class C: is_audio_clip = False; looping = True; length = 4.0; start_marker = 0.0; loop_start = 0.0; loop_end = 4.0; playing_position = 5.0
r = lambda t: tuple(round(x, 6) if isinstance(x, float) else x for x in t)
assert r(m.clip_progress(C, 120)) == (1.5, 2.0, True)   # 4 beats @120 = 2 s, 1 beat in (position 5 wraps to 1) -> 1.5 s left
C.looping = False; C.playing_position = 9.0
assert r(m.clip_progress(C, 120)) == (0.0, 2.0, False)   # one-shot clamps at its end
C.looping = True; C.start_marker = 1.0   # Start marker 1 beat into a 0-4 loop
C.playing_position = 1.0
assert r(m.clip_progress(C, 120)) == (2.0, 2.0, True)   # empty bar at the Start marker
C.playing_position = 3.9
assert r(m.clip_progress(C, 120)) == (0.55, 2.0, True)   # still before the wrap
C.playing_position = 0.5
assert r(m.clip_progress(C, 120)) == (0.25, 2.0, True)   # after the wrap to Loop start the bar is near full, not empty
C.playing_position = 0.9
assert r(m.clip_progress(C, 120)) == (0.05, 2.0, True)   # full just before the Start marker comes round again
print("PASS")
