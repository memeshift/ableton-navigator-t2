SYSEX_ID = 0x7D
MSG_SCENES = 0x02
NAME_LEN = 20


def name_bytes(name):
    text = ''.join(c if 0x20 <= ord(c) <= 0x7E else '?' for c in name.encode('ascii', 'replace').decode('ascii'))
    return [ord(c) for c in text[:NAME_LEN].ljust(NAME_LEN)]


def tenths(seconds):
    return max(0, min(0x3FFF, round(seconds * 10)))


def clip_progress(clip, song_tempo):
    """(seconds left in this pass, seconds in a full pass, is looping).

    playing_position and length share a unit (beats for MIDI and warped audio,
    seconds for unwarped audio), so only the final conversion depends on which.
    A looping clip is measured from its Start marker and wraps at a full loop's
    length, so the bar is empty at the Start marker on every pass and full just
    before the playhead returns to it; the jump back to Loop start falls
    part-way across. A one-shot runs from its start to its end.
    """
    length = clip.length
    if length <= 0:
        return 0.0, 0.0, False
    looping = bool(getattr(clip, 'looping', True))
    if looping:
        played = (clip.playing_position - clip.start_marker) % length
    else:
        played = max(0.0, min(length, clip.playing_position - clip.loop_start))
    left = length - played
    if clip.is_audio_clip and not getattr(clip, 'warping', True):
        return left, length, looping
    if song_tempo <= 0:
        return 0.0, 0.0, looping
    per_beat = 60.0 / song_tempo
    return left * per_beat, length * per_beat, looping


def scene_message(name, index, playing=False, bpm=120.0, beat=None,
                  scene_bpm=120.0, sig=(4, 4), progress=(0, 0.0, 0.0), track=('', -1, 0)):
    """F0 7D 02 <num hi> <num lo> <playing> <tempo hi> <tempo lo> <phase hi> <phase lo> <scene tempo hi> <scene tempo lo> <sig num> <sig den> <name> <prog state> <left hi> <left lo> <total hi> <total lo> <track num hi> <track num lo> <track kind> <track name> F7.

    track is (name, 0-based index or -1 when the selected track is not in song.tracks, kind): the track num is index + 1 as two 7-bit bytes (0 = none), kind is 0 audio, 1 MIDI, 2 open group, 3 folded group.

    num is the 1-based selected scene as two 7-bit bytes, playing is 0 (not playing), 1 (playing) or 2 (empty scene), tempo is BPM x 10 as two 7-bit bytes, phase is the fractional part of `beat` x 16383 as two 7-bit bytes (0x3FFF = transport stopped, no phase), scene tempo is BPM x 10 like tempo. progress is (state, seconds left in this pass, seconds in a full pass): state 0 none, 1 looping clip, 2 one-shot, 3 one-shot finished; times are tenths of a second as two 7-bit bytes."""
    tempo, scene_tempo = (max(0, min(0x3FFF, round(b * 10))) for b in (bpm, scene_bpm))
    phase = 0x3FFF if beat is None else min(0x3FFE, int((beat % 1.0) * 0x3FFF))
    body = [(index + 1) >> 7, (index + 1) & 0x7F, int(playing), tempo >> 7, tempo & 0x7F, phase >> 7, phase & 0x7F,
            scene_tempo >> 7, scene_tempo & 0x7F, sig[0] & 0x7F, sig[1] & 0x7F]
    state, left, total = progress
    tail = [int(state), tenths(left) >> 7, tenths(left) & 0x7F, tenths(total) >> 7, tenths(total) & 0x7F]
    tname, tindex, tkind = track
    trk = [(tindex + 1) >> 7, (tindex + 1) & 0x7F, int(tkind)]
    return tuple([0xF0, SYSEX_ID, MSG_SCENES] + body + name_bytes(name) + tail + trk + name_bytes(tname) + [0xF7])
