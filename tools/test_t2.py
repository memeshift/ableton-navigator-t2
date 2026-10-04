import importlib.util, pathlib
p = pathlib.Path(__file__).parent.parent / "remote-script/NavigatorT2/protocol.py"
s = importlib.util.spec_from_file_location("protocol", p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)

msg = m.scene_message(["Intro", "Verse", "Chorus"], 0)
assert len(msg) == 3 + 60 + 1 and msg[0] == 0xF0 and msg[-1] == 0xF7 and msg[1:3] == (0x7D, 2)
assert len(msg) == 64   # firmware onSysEx() checks 3 + 3*NAME_LEN + 1
assert all(b < 0x80 for b in msg[1:-1])
txt = lambda k: bytes(msg[3 + 20 * k:23 + 20 * k]).decode().rstrip()
assert (txt(0), txt(1), txt(2)) == ("", "Intro", "Verse")          # blank before first
assert bytes(m.scene_message(["a", "b"], 1)[43:63]).decode().strip() == ""   # blank after last
assert bytes(m.name_bytes("Café ☃" * 5)).decode().count("?") > 0 and len(m.name_bytes("x" * 99)) == 20
print("PASS")
