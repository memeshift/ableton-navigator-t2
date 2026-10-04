import importlib.util, pathlib
p = pathlib.Path(__file__).parent.parent / "remote-script/NavigatorT2/protocol.py"
s = importlib.util.spec_from_file_location("protocol", p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)

msg = m.scene_message("Intro", 0)
assert len(msg) == 14 + 20 + 1 and msg[0] == 0xF0 and msg[-1] == 0xF7 and msg[1:3] == (0x7D, 2)
assert len(msg) == 35   # firmware onSysEx() checks 14 + NAME_LEN + 1
assert all(b < 0x80 for b in msg[1:-1])
assert bytes(msg[14:34]).decode().rstrip() == "Intro"
assert bytes(m.name_bytes("Café ☃" * 5)).decode().count("?") > 0 and len(m.name_bytes("x" * 99)) == 20
assert msg[3:8] == (0, 1, 0, 9, 48) and m.scene_message("x", 150, True, 128.5)[3:8] == (1, 23, 1, 10, 5)   # num 1 / 151, playing flag, 120.0 / 128.5 BPM
assert msg[8:10] == (127, 127) and m.scene_message("x", 0, False, 120, 2.25)[8:10] == (31, 127)   # no beat -> 0x3FFF; beat 2.25 -> phase 4095
assert m.scene_message("x", 0, False, 120, 7.0)[8:10] == (0, 0) and m.scene_message("x", 0, False, 120, 0.99999)[8:10] != (127, 127)
assert msg[10:14] == (9, 48, 4, 4) and m.scene_message("x", 0, False, 120, None, 128.5, (7, 8))[10:14] == (10, 5, 7, 8)   # 120.0 4/4 default; 128.5 7/8
assert m.scene_message("x", 0, 2)[5] == 2 and m.scene_message("x", 0, True)[5] == 1 and m.scene_message("x", 0, 0)[5] == 0   # playing byte: 0 / 1 / 2 = empty scene
print("PASS")
