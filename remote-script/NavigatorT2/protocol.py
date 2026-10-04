SYSEX_ID = 0x7D
MSG_SCENES = 0x02
NAME_LEN = 20


def name_bytes(name):
    text = ''.join(c if 0x20 <= ord(c) <= 0x7E else '?' for c in name.encode('ascii', 'replace').decode('ascii'))
    return [ord(c) for c in text[:NAME_LEN].ljust(NAME_LEN)]


def scene_message(names, index):
    """F0 7D 02 <prev> <cur> <next> F7; neighbours past either end are blank."""
    def at(i):
        return names[i] if 0 <= i < len(names) else ''
    body = []
    for i in (index - 1, index, index + 1):
        body += name_bytes(at(i))
    return tuple([0xF0, SYSEX_ID, MSG_SCENES] + body + [0xF7])
