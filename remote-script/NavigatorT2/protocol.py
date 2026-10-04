SYSEX_ID = 0x7D
MSG_SCENES = 0x02
NAME_LEN = 20


def name_bytes(name):
    text = ''.join(c if 0x20 <= ord(c) <= 0x7E else '?' for c in name.encode('ascii', 'replace').decode('ascii'))
    return [ord(c) for c in text[:NAME_LEN].ljust(NAME_LEN)]


def scene_message(name, index, playing=False, bpm=120.0, beat=None,
                  scene_bpm=120.0, sig=(4, 4)):
    """F0 7D 02 <num hi> <num lo> <playing> <tempo hi> <tempo lo> <phase hi> <phase lo> <scene tempo hi> <scene tempo lo> <sig num> <sig den> <name> F7.

    num is the 1-based selected scene as two 7-bit bytes, playing is 0 (not playing), 1 (playing) or 2 (empty scene), tempo is BPM x 10 as two 7-bit bytes, phase is the fractional part of `beat` x 16383 as two 7-bit bytes (0x3FFF = transport stopped, no phase), scene tempo is BPM x 10 like tempo."""
    tempo, scene_tempo = (max(0, min(0x3FFF, round(b * 10))) for b in (bpm, scene_bpm))
    phase = 0x3FFF if beat is None else min(0x3FFE, int((beat % 1.0) * 0x3FFF))
    body = [(index + 1) >> 7, (index + 1) & 0x7F, int(playing), tempo >> 7, tempo & 0x7F, phase >> 7, phase & 0x7F,
            scene_tempo >> 7, scene_tempo & 0x7F, sig[0] & 0x7F, sig[1] & 0x7F]
    return tuple([0xF0, SYSEX_ID, MSG_SCENES] + body + name_bytes(name) + [0xF7])
