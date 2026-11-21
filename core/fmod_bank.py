"""Reader for the FMOD Studio bank metadata the dating-scene sounds need (chunk layouts follow the open-source FModBankParser
by Masusder, used as a reference): the strings bank (path <-> GUID radix tree) and, per sound bank, which clips an event plays
and when (event -> timeline -> placed instruments -> waveform / playlist -> waveform resource -> FSB subsound).
"""
import struct
from typing import Any, Dict, List, Optional, Tuple

SAMPLE_RATE = 48000  # timeline positions are in samples at the game's 48 kHz


def read_x16(b: bytes, p: int) -> Tuple[int, int]:
    """FMOD's variable length count: u16, and when its high bit is set 15 more bits follow in a second u16."""
    low = struct.unpack_from('<H', b, p)[0]
    p += 2
    if low & 0x8000:
        high = struct.unpack_from('<H', b, p)[0]
        return (low & 0x7FFF) | (high << 15), p + 2
    return low, p


def _elem_list(b: bytes, p: int, size: int) -> Tuple[List[bytes], int]:
    raw, p = read_x16(b, p)
    count = raw >> 1
    if count <= 0:
        return [], p
    p += 2  # payload size
    return [b[p + size * i:p + size * (i + 1)] for i in range(count)], p + size * count


def parse_chunks(b: bytes, offset: int = 12, end: Optional[int] = None) -> List[Dict[str, Any]]:
    """RIFF-like chunks (sizes padded to even); LIST chunks hold a 4-byte kind and then sub-chunks."""
    end = len(b) if end is None else end
    nodes = []
    while offset + 8 <= end:
        tag = b[offset:offset + 4].decode('latin1')
        size = struct.unpack_from('<I', b, offset + 4)[0]
        body = offset + 8
        node: Dict[str, Any] = {'tag': tag, 'off': body, 'size': size, 'kids': []}
        if tag == 'LIST':
            node['kids'] = parse_chunks(b, body + 4, min(end, body + size))
        nodes.append(node)
        offset = body + size + (size & 1)
    return nodes


def _metadata_end(b: bytes) -> int:
    i = b.find(b'FSB5')
    return len(b) if i < 0 else i - 8  # the audio block (SND chunk) follows the metadata


# ---- strings bank ---------------------------------------------------------------------------------------------------

def read_strings(b: bytes) -> Dict[bytes, str]:
    """GUID (16 raw bytes) -> path, from a `.strings.bank` (a packed radix tree: nodes, guids, string blob, leaf/parent links)."""
    found = next((n for n in _walk(parse_chunks(b, 12, len(b))) if n['tag'] == 'STDT'), None)
    if not found:
        return {}
    p = found['off']
    kind = struct.unpack_from('<I', b, p)[0]
    p += 4
    raw, p = read_x16(b, p)
    node_count = raw >> 1
    p += 2
    nodes = [struct.unpack_from('<II', b, p + 8 * i) for i in range(node_count)]
    p += 8 * node_count
    raw, p = read_x16(b, p)
    guid_count = raw >> 1
    p += 2
    guids = [b[p + 16 * i:p + 16 * i + 16] for i in range(guid_count)]
    p += 16 * guid_count
    blob_size, p = read_x16(b, p)
    blob = b[p:p + blob_size]
    p += blob_size
    if kind != 1:
        raise ValueError('Only 24-bit radix string tables are supported')

    def array24():
        nonlocal p
        count, p = read_x16(b, p)
        values = [b[p + 3 * i] | (b[p + 3 * i + 1] << 8) | (b[p + 3 * i + 2] << 16) for i in range(count)]
        p += 3 * count
        return values

    leaves, parents = array24(), array24()
    NONE = 0xFFFFFF
    paths: Dict[bytes, str] = {}
    for index, guid in enumerate(guids):
        node, parts, guard = leaves[index], [], 0
        while node != NONE and node < node_count and guard < 100000:
            offset = nodes[node][0] & 0xFFFFFF
            if offset != NONE:
                end = blob.find(b'\0', offset)
                parts.append(blob[offset:end if end >= 0 else len(blob)].decode('utf-8', 'replace'))
            node = parents[node]
            guard += 1
        paths[guid] = ''.join(reversed(parts))
    return paths


def _walk(nodes):
    for node in nodes:
        yield node
        yield from _walk(node['kids'])


# ---- sound banks: events -> clips -----------------------------------------------------------------------------------

_BODY = {'WAIB': 'wave', 'MUIB': 'multi', 'SPIB': 'scatter'}


def _skip_list(b: bytes, p: int, size: int) -> int:
    raw, p = read_x16(b, p)
    count = raw >> 1
    return p if count <= 0 else p + 2 + count * size


def _bus_chain_db(buses: Dict[bytes, Dict[str, Any]], guid: bytes) -> float:
    """Sum of the fader levels (dB) from a bus up through the buses it routes to (inside this bank)."""
    total, seen = 0.0, set()
    while guid in buses and guid not in seen and len(seen) < 32:
        seen.add(guid)
        total += buses[guid]['vol']
        guid = buses[guid]['out']
    return total


def _fade_seconds(curve_points: List[Tuple[int, float]]) -> Tuple[float, float]:
    """(fade-in, fade-out) seconds from an automation curve over the timeline (positions are sample counts, `y` goes 0->1 for
    a fade-in and 1->0 for a fade-out)."""
    if len(curve_points) < 2:
        return 0.0, 0.0
    (x0, y0), (x1, y1) = curve_points[0], curve_points[-1]
    seconds = max(0, x1 - x0) / SAMPLE_RATE
    return (seconds, 0.0) if y1 > y0 else (0.0, seconds)


def load_bank(b: bytes) -> Dict[str, Any]:
    """Index a bank's events, timelines, instruments (with their level, fades, trim and routing) and waveform resources."""
    root = parse_chunks(b, 12, _metadata_end(b))
    nodes = list(_walk(root))
    events: Dict[bytes, Dict[str, Any]] = {}
    waves: Dict[bytes, int] = {}
    timelines: Dict[bytes, List[Tuple[bytes, int, int]]] = {}
    buses: Dict[bytes, Dict[str, Any]] = {}
    curves: Dict[bytes, List[Tuple[int, float]]] = {}
    controllers: Dict[bytes, bytes] = {}
    randoms: Dict[bytes, float] = {}
    # pass 1: everything an instrument can point at
    for node in nodes:
        tag, o = node['tag'], node['off']
        if tag == 'EVTB':
            events[b[o:o + 16]] = {'timeline': b[o + 32:o + 48]}
        elif tag == 'WAV ':
            waves[b[o:o + 16]] = struct.unpack_from('<ii', b, o + 18)[1]  # subsound index in the FSB
        elif tag == 'TLNB':
            p, boxes = o + 16, []
            for _ in range(2):  # trigger boxes, then the time-locked ones (the placed instruments)
                raw, p = read_x16(b, p)
                count = raw >> 1
                if count > 0:
                    p += 2
                    boxes += [(b[p + 24 * k:p + 24 * k + 16], *struct.unpack_from('<II', b, p + 24 * k + 16)) for k in range(count)]
                    p += 24 * count
            timelines[b[o:o + 16]] = boxes
        elif tag == 'CURV':
            raw, p = read_x16(b, o + 32)
            count = raw >> 1
            p += 2 if count else 0
            # points: position (sample count, stored as u32), value, shape, type
            curves[b[o:o + 16]] = [(struct.unpack_from('<I', b, p + 16 * i)[0], struct.unpack_from('<f', b, p + 16 * i + 4)[0]) for i in range(count)]
        elif tag == 'CTRL':
            controllers[b[o:o + 16]] = b[o + 32:o + 48]
        elif tag == 'MODB' and node['size'] >= 54 and struct.unpack_from('<ii', b, o + 34)[1] == 1:  # random modulator on a property
            randoms[b[o:o + 16]] = struct.unpack_from('<f', b, o + 50)[0]
        elif tag == 'LIST':
            body = next((k for k in node['kids'] if k['tag'] in ('IBSB', 'GBSB', 'MBSB', 'RBSB')), None)
            bus = next((k for k in node['kids'] if k['tag'] == 'BUS '), None)
            if body and bus:
                bo = body['off']
                buses[b[bo:bo + 16]] = {'out': b[bo + 18:bo + 34], 'vol': struct.unpack_from('<f', b, _skip_list(b, _skip_list(b, bus['off'] + 8, 16), 16) + 2)[0]}
    # pass 2: instruments
    instruments: Dict[bytes, Dict[str, Any]] = {}
    for node in nodes:
        if node['tag'] != 'LIST' or not any(k['tag'] in _BODY for k in node['kids']):
            continue
        kids = {k['tag']: k for k in node['kids']}
        body = next(k for k in node['kids'] if k['tag'] in _BODY)
        guid = b[body['off']:body['off'] + 16]
        info: Dict[str, Any] = {'kind': _BODY[body['tag']], 'children': [], 'gain_db': 0.0, 'semitones': 0.0, 'chance': 100.0,
                                'bus_db': 0.0, 'trim': 0, 'fade_in': 0.0, 'fade_out': 0.0, 'jitter_db': 0.0}
        if info['kind'] == 'wave':
            info['wave'] = b[body['off'] + 16:body['off'] + 32]
        if 'PLST' in kids:
            entries, _ = _elem_list(b, kids['PLST']['off'] + 8, 20)
            info['children'] = [e[:16] for e in entries]
        if 'INST' in kids and kids['INST']['size'] >= 40:
            inst, size = kids['INST']['off'], kids['INST']['size']
            info['gain_db'], info['semitones'] = struct.unpack_from('<ff', b, inst + 16)
            info['chance'] = struct.unpack_from('<f', b, inst + 36)[0]
            info['timeline'] = b[inst:inst + 16]
            route = next((off for off in range(32, size - 15) if b[inst + off:inst + off + 16] in buses), None)
            if route is not None:
                info['bus_db'] = _bus_chain_db(buses, b[inst + route:inst + route + 16])
                if size >= route + 32:
                    info['trim'] = struct.unpack_from('<I', b, inst + route + 28)[0]  # left trim: start offset into the clip, in samples
        for sub in node['kids']:  # properties: 4 = fade curves, 1 = volume (random modulator)
            for prop in ([sub] + sub['kids']):
                if prop['tag'] != 'PROP':
                    continue
                po = prop['off']
                index = struct.unpack_from('<I', b, po)[0]
                count_raw, p = read_x16(b, po + 24)
                n_ctrl = count_raw >> 1
                p += 2 if n_ctrl else 0
                ctrl_ids = [b[p + 16 * i:p + 16 * i + 16] for i in range(n_ctrl)]
                p += 16 * n_ctrl
                count_raw, p = read_x16(b, p)
                n_mod = count_raw >> 1
                p += 2 if n_mod else 0
                mod_ids = [b[p + 16 * i:p + 16 * i + 16] for i in range(n_mod)]
                if index == 4:
                    for c in ctrl_ids:
                        fade_in, fade_out = _fade_seconds(curves.get(controllers.get(c, b''), []))
                        info['fade_in'], info['fade_out'] = max(info['fade_in'], fade_in), max(info['fade_out'], fade_out)
                elif index == 1:
                    info['jitter_db'] = max([randoms.get(m, 0.0) for m in mod_ids] + [info['jitter_db']])
        instruments[guid] = info
    children = {c for info in instruments.values() for c in info['children']}
    by_timeline: Dict[bytes, List[bytes]] = {}
    for guid, info in instruments.items():
        if guid not in children and 'timeline' in info:
            by_timeline.setdefault(info['timeline'], []).append(guid)
    return {'events': events, 'instruments': instruments, 'waves': waves, 'timelines': timelines, 'by_timeline': by_timeline}


def event_plan(bank: Dict[str, Any], event_guid: bytes) -> Optional[List[Dict[str, Any]]]:
    """What the event plays: one entry per placed instrument with its start (seconds), gain, pitch, trigger chance and the
    clip (subsound) indices it picks one of (`one`) or plays together (`all`)."""
    event = bank['events'].get(event_guid)
    if not event:
        return None

    def clips(guid: bytes, depth: int = 0) -> List[int]:
        info = bank['instruments'].get(guid)
        if not info or depth > 8:
            return []
        if info['kind'] == 'wave':
            index = bank['waves'].get(info['wave'])
            return [] if index is None else [index]
        return [c for child in info['children'] for c in clips(child, depth + 1)]

    layers = []
    placed = sorted(bank['timelines'].get(event['timeline'], []), key=lambda box: box[1])
    for guid, start, length in placed or [(g, 0, 0) for g in bank['by_timeline'].get(event['timeline'], [])]:
        info = bank['instruments'].get(guid)
        found = clips(guid) if info else []
        if not found:
            continue
        layers.append({
            'start': round(start / SAMPLE_RATE, 4), 'length': round(length / SAMPLE_RATE, 4), 'trim': info['trim'],
            # level = the instrument's own volume + the faders of the track buses it routes through (dB -> linear)
            'gain': round(10 ** ((info['gain_db'] + info['bus_db']) / 20), 4), 'jitter_db': round(info['jitter_db'], 2),
            'rate': round(2 ** (info['semitones'] / 12), 4), 'chance': round(max(0.0, min(100.0, info['chance'])) / 100, 3),
            'fade_in': round(info['fade_in'], 4), 'fade_out': round(info['fade_out'], 4),
            'pick': 'one' if info['kind'] != 'wave' else 'all', 'clips': found})
    return layers
