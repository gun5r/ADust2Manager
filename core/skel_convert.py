"""Spine binary skeleton converter: 4.1 (.skel) -> 4.2.

The game moved from Spine 4.1 to 4.2 and its runtime refuses skeleton data of another minor version, so mods still exported as 4.1 do
not load in game. 4.2 changed the binary layout (flag bytes, new constraint/skin fields, reordered attachment fields) but added no
feature the old data could not express, so a 4.1 file can be re-encoded without loss. The layouts below follow the official spine-ts
SkeletonBinary.ts of the 4.1 and 4.2 branches; the strings table is kept as it is, so every string reference stays valid.

This module is the pure format conversion (bytes in, bytes out). Files and the cache of converted ones are in skel_files.py.
"""
import json
import struct

TARGET_VERSION = "4.2.43"  # what the game's own files carry; the 4.2 runtimes accept any 4.2.x
REFERENCE_SCALE = 100.0  # the editor's default
REVISION = "1"  # part of the prepare-cache identity: bump it when the converter's output changes

# Attachment flag byte of 4.2: the low three bits are the type; the others say which optional fields follow. The top bit (128) means
# something different per type (region: rotation, mesh: weighted, linked mesh: inherit timelines).
NAME, PATH, COLOR, SEQUENCE, TOP = 8, 16, 32, 64, 128
WHITE = b"\xff\xff\xff\xff"
STEPPED, BEZIER = 1, 2  # curve types of the 4.1 timelines
# the 4.2 IK timeline keeps the curve in its frame flags
IK_STEPPED, IK_BEZIER = 0x40, 0x80

# slot timeline type -> (bytes per frame value, bezier curves); type 0 (attachment) has neither
SLOT_TIMELINES = {1: (4, 4), 2: (3, 3), 3: (7, 7), 4: (6, 6), 5: (1, 1)}
TWO_VALUES = (1, 4, 7)  # bone timelines of translate, scale and shear carry x and y; the others one value


class SkelError(Exception):
    pass


def _var(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _varlist(values) -> bytes:
    return b"".join(_var(v) for v in values)


def _lit(raw: bytes) -> bytes:
    """A string as the 4.2 reader wants it: byte count + 1, then the bytes (the same encoding the strings table uses)."""
    return _var(len(raw) + 1) + raw


def _f(b: bytes) -> float:
    return struct.unpack(">f", b)[0]


def _implied_one(value: float, present: int, explicit: int) -> int:
    """Flag bits for a float that 4.2 leaves out when it is 0 and implies when it is 1: nothing, `present`, or both (the value follows)."""
    return 0 if value == 0 else present if value == 1 else present | explicit


class _In:
    def __init__(self, data: bytes):
        self.b = data
        self.i = 0

    def raw(self, n: int) -> bytes:
        if n < 0 or self.i + n > len(self.b):
            raise SkelError("unexpected end of the skeleton file")
        v = self.b[self.i:self.i + n]
        self.i += n
        return v

    def u8(self) -> int:
        return self.raw(1)[0]

    def var(self) -> int:
        r = shift = 0
        for _ in range(5):
            b = self.u8()
            r |= (b & 0x7F) << shift
            if not b & 0x80:
                return r
            shift += 7
        return r

    def var_raw(self):
        start = self.i
        v = self.var()
        return v, self.b[start:self.i]

    def string_raw(self):
        """(None for a null string, else its bytes; the whole field as stored, length prefix included)."""
        start = self.i
        n = self.var()
        body = b"" if n <= 1 else self.raw(n - 1)
        return (None if n == 0 else body), self.b[start:self.i]


def skel_version(data: bytes) -> str | None:
    """The Spine version a binary .skel was exported with ('4.1.11'), or None when it is not a Spine binary (JSON, empty)."""
    try:
        i = _In(data)
        i.raw(8)
        text = (i.string_raw()[0] or b"").decode("utf-8", "replace")
        return text if text[:1].isdigit() and "." in text else None
    except SkelError:
        return None


class _Transcoder:
    """Reads a 4.1 file once, front to back, and writes the 4.2 one next to it. Mostly it copies; what changed is spelled out below."""

    def __init__(self, data: bytes):
        self.i = _In(data)
        self.o = bytearray()
        self.table = []  # strings table, as stored (length prefix + bytes)
        self.nonessential = False
        self.event_audio = []  # per event: does it have an audio file (its timeline entries then carry volume and balance)
        self.skin_names = []
        self.has_default = False
        # A linked mesh names its skin; 4.2 wants the skin's index, which is not known until all skins are read. Its place in the output is
        # remembered (with the string reference) and filled in at the end.
        self.linked = []
        self.pending = []

    # -- copy helpers --------------------------------------------------------------------------------------
    def copy_var(self) -> int:
        v, raw = self.i.var_raw()
        self.o += raw
        return v

    def copy_raw(self, n: int) -> None:
        self.o += self.i.raw(n)

    def copy_string(self) -> None:
        self.o += self.i.string_raw()[1]

    def copy_list(self) -> None:
        for _ in range(self.copy_var()):
            self.copy_var()

    def string_at(self, ref: int) -> bytes:
        if not 0 < ref <= len(self.table):
            raise SkelError("a string reference outside the strings table")
        return self.table[ref - 1]

    def ref_literal(self, ref: int) -> None:
        """A strings-table reference (index + 1, 0 = null) written the 4.2 way: as the text itself."""
        self.o += b"\x00" if ref == 0 else self.string_at(ref)

    def extra(self, n: int) -> bytes:
        """`n` bytes of editor-only data, when the file has any."""
        return self.i.raw(n) if self.nonessential else b""

    # -- the file ------------------------------------------------------------------------------------------
    def run(self) -> None:
        i, o = self.i, self.o
        o += i.raw(8)  # hash
        version = i.string_raw()[0] or b""
        if not version.startswith(b"4.1"):
            raise SkelError(f"not a Spine 4.1 skeleton (found {version.decode('utf-8', 'replace') or 'nothing'})")
        o += _lit(TARGET_VERSION.encode())
        self.copy_raw(16)  # x, y, width, height
        o += struct.pack(">f", REFERENCE_SCALE)
        self.nonessential = bool(i.u8())
        o.append(int(self.nonessential))
        if self.nonessential:
            self.copy_raw(4)  # fps
            self.copy_string()  # images path
            self.copy_string()  # audio path
        for _ in range(self.copy_var()):
            field = i.string_raw()[1]
            self.table.append(field)
            o += field
        self.bones()
        self.slots()
        self.ik()
        self.transform()
        self.path()
        o += b"\x00"  # physics constraints: none (new in 4.2)
        self.skins()
        self.events()
        for _ in range(self.copy_var()):
            self.copy_string()
            self.animation()
        if i.i != len(i.b):
            raise SkelError(f"{len(i.b) - i.i} unread bytes at the end of the file: not understood as 4.1 data")
        self.fill_skin_indexes()

    def fill_skin_indexes(self) -> None:
        offset = 1 if self.has_default else 0
        index = {name: k + offset for k, name in enumerate(self.skin_names)}
        for position, ref in reversed(self.linked):  # from the back, so the earlier positions stay valid
            self.o[position:position] = _var(index.get(self.string_at(ref), 0) if ref else 0)

    def bones(self) -> None:
        for k in range(self.copy_var()):
            self.copy_string()
            if k:
                self.copy_var()  # parent
            self.copy_raw(32)  # rotation, x, y, scaleX, scaleY, shearX, shearY, length
            mode = self.i.var()  # transform mode, a varint in 4.1 and one byte (called inherit) in 4.2
            if mode > 255:
                raise SkelError("a bone transform mode that is not a byte")
            self.o.append(mode)
            self.copy_raw(1)  # skin required
            if self.nonessential:
                self.copy_raw(4)  # color
                self.o += b"\x00\x01"  # icon (none), visible

    def slots(self) -> None:
        for _ in range(self.copy_var()):
            self.copy_string()
            self.copy_var()  # bone
            self.copy_raw(8)  # color, dark color
            self.copy_var()  # attachment name
            self.copy_var()  # blend mode
            if self.nonessential:
                self.o.append(1)  # visible

    def ik(self) -> None:
        i, o = self.i, self.o
        for _ in range(self.copy_var()):
            self.copy_string()
            self.copy_var()  # order
            skin_required = i.u8()
            self.copy_list()  # bones
            self.copy_var()  # target
            mix, soft = i.raw(4), i.raw(4)
            bend, compress, stretch, uniform = i.u8(), i.u8(), i.u8(), i.u8()
            # one flags byte replaces the booleans; mix and softness follow only when they are not 1 / 0
            flags = (1 if skin_required else 0) | (2 if bend == 1 else 0) | (4 if compress else 0) | (8 if stretch else 0) | (16 if uniform else 0)
            flags |= _implied_one(_f(mix), 32, 64) | (128 if _f(soft) != 0 else 0)
            o.append(flags)
            o += (mix if flags & 64 else b"") + (soft if flags & 128 else b"")

    def transform(self) -> None:
        i, o = self.i, self.o
        for _ in range(self.copy_var()):
            self.copy_string()
            self.copy_var()  # order
            skin_required = i.u8()
            self.copy_list()  # bones
            self.copy_var()  # target
            local, relative = i.u8(), i.u8()
            values = [i.raw(4) for _ in range(12)]  # offsets (rotation, x, y, scaleX, scaleY, shearY), then mixes (same six)
            present = [_f(v) != 0 for v in values]  # 4.2 leaves out the ones that are 0
            first = (1 if skin_required else 0) | (2 if local else 0) | (4 if relative else 0)
            first |= sum(8 << k for k in range(5) if present[k])
            second = sum(1 << (k - 5) for k in range(5, 12) if present[k])
            o.append(first)
            o += b"".join(values[k] for k in range(5) if present[k])
            o.append(second)
            o += b"".join(values[k] for k in range(5, 12) if present[k])

    def path(self) -> None:
        i, o = self.i, self.o
        for _ in range(self.copy_var()):
            self.copy_string()
            self.copy_var()  # order
            self.copy_raw(1)  # skin required
            self.copy_list()  # bones
            self.copy_var()  # target slot
            position, spacing, rotate = i.var(), i.var(), i.var()  # three modes become bit fields of one byte
            offset = i.raw(4)
            flags = (position & 1) | ((spacing & 3) << 1) | ((rotate & 3) << 3) | (128 if _f(offset) != 0 else 0)
            o.append(flags)
            o += offset if flags & 128 else b""
            self.copy_raw(20)  # position, spacing, mixRotate, mixX, mixY

    # -- skins and attachments -----------------------------------------------------------------------------
    def skins(self) -> None:
        default_slots = self.copy_var()
        self.has_default = default_slots > 0
        self.skin_slots(default_slots)
        for _ in range(self.copy_var()):
            ref = self.i.var()
            self.skin_names.append(self.string_at(ref) if ref else b"")
            self.ref_literal(ref)  # the name is the text itself in 4.2
            if self.nonessential:
                self.o += struct.pack(">I", 0x99999999)  # skin color (new in 4.2)
            for _ in range(4):
                self.copy_list()  # bones, then the ik, transform and path constraints the skin needs
            self.o += b"\x00"  # physics constraints of the skin (new)
            self.skin_slots(self.copy_var())

    def skin_slots(self, slot_count: int) -> None:
        for _ in range(slot_count):
            self.copy_var()  # slot index
            for _ in range(self.copy_var()):
                self.copy_var()  # attachment name (strings reference)
                self.attachment()

    def attachment(self) -> None:
        """4.2 writes a flags byte (type, which optional fields follow) and then the fields; each reader below gives its flags and fields."""
        name_ref, name_raw = self.i.var_raw()
        kind = self.i.u8()
        if kind >= len(ATTACHMENT_READERS):
            raise SkelError(f"unknown attachment type {kind}")
        flags, body = getattr(self, ATTACHMENT_READERS[kind])()
        self.o.append(kind | (NAME if name_ref else 0) | flags)
        if name_ref:
            self.o += name_raw
        start = len(self.o)
        self.o += body
        self.linked += [(start + offset, ref) for offset, ref in self.pending]
        self.pending.clear()

    def optional_ref(self):
        """A strings reference that is only written when set: its bytes, or None."""
        ref, raw = self.i.var_raw()
        return raw if ref else None

    def sequence(self):
        """A texture sequence (four varints) behind a boolean in 4.1: its bytes, or None."""
        return b"".join(self.i.var_raw()[1] for _ in range(4)) if self.i.u8() else None

    def vertices(self, count: int, weighted: bool) -> bytes:
        """The bytes of `count` vertices as stored (a weighted one lists its bones and weights); the layout did not change."""
        i = self.i
        start = i.i
        if weighted:
            for _ in range(count):
                for _ in range(i.var()):
                    i.var()
                    i.raw(12)
        else:
            i.raw(8 * count)
        return i.b[start:i.i]

    def shorts(self, n: int) -> list:
        return [int.from_bytes(self.i.raw(2), "big") for _ in range(n)]

    @staticmethod
    def style(path, color: bytes, sequence):
        """Flags and bytes of the optional leading fields of regions, meshes and linked meshes: path, color (when not white), sequence."""
        flags = (PATH if path else 0) | (COLOR if color != WHITE else 0) | (SEQUENCE if sequence is not None else 0)
        return flags, (path or b"") + (color if color != WHITE else b"") + (sequence or b"")

    def region(self):
        i = self.i
        path, rotation, geometry, color = self.optional_ref(), i.raw(4), i.raw(24), i.raw(4)
        flags, head = self.style(path, color, self.sequence())
        turned = _f(rotation) != 0
        return flags | (TOP if turned else 0), head + (rotation if turned else b"") + geometry

    def bounding_box(self):
        count, weighted = self.i.var(), self.i.u8()
        return (16 if weighted else 0), _var(count) + self.vertices(count, weighted) + self.extra(4)

    def mesh(self):
        i = self.i
        path, color, count = self.optional_ref(), i.raw(4), i.var()
        uvs = i.raw(8 * count)
        triangles = self.shorts(i.var())
        weighted = i.u8()
        vertices = self.vertices(count, weighted)
        hull, sequence = i.var(), self.sequence()
        # 4.2 does not store the number of triangle indices, it derives it from the hull length: (2 * vertices - hull - 2) * 3. A mesh that
        # does not follow that rule (an unused vertex, say) gets the hull length that makes it do so; the hull only draws outlines in the
        # editor, it is never used to render.
        if len(triangles) != (2 * count - hull - 2) * 3:
            if len(triangles) % 3 or 2 * count - 2 - len(triangles) // 3 < 0:
                raise SkelError("a mesh whose triangles cannot be re-encoded")
            hull = 2 * count - 2 - len(triangles) // 3
        flags, head = self.style(path, color, sequence)
        body = head + _var(hull) + _var(count) + vertices + uvs + _varlist(triangles)
        if self.nonessential:
            edges = self.shorts(i.var())
            body += _var(len(edges)) + _varlist(edges) + i.raw(8)  # edges, width, height
        return flags | (TOP if weighted else 0), body

    def linked_mesh(self):
        i = self.i
        path, color, skin_ref = self.optional_ref(), i.raw(4), i.var()
        parent, inherit, sequence = i.var_raw()[1], i.u8(), self.sequence()
        flags, head = self.style(path, color, sequence)
        self.pending.append((len(head), skin_ref))  # the skin index goes right after the head, once the skins are all known
        return flags | (TOP if inherit else 0), head + parent + self.extra(8)

    def path_attachment(self):
        i = self.i
        closed, constant, count, weighted = i.u8(), i.u8(), i.var(), i.u8()
        flags = (16 if closed else 0) | (32 if constant else 0) | (64 if weighted else 0)
        return flags, _var(count) + self.vertices(count, weighted) + i.raw(4 * (count // 3)) + self.extra(4)  # ... and the curve lengths

    def point(self):
        return 0, self.i.raw(12) + self.extra(4)

    def clipping(self):
        end_slot, count, weighted = self.i.var_raw()[1], self.i.var(), self.i.u8()
        return (16 if weighted else 0), end_slot + _var(count) + self.vertices(count, weighted) + self.extra(4)

    # -- events and animations -----------------------------------------------------------------------------
    def events(self) -> None:
        for _ in range(self.copy_var()):
            self.ref_literal(self.i.var())  # the name is the text itself in 4.2
            self.copy_var()  # int value (zig-zag)
            self.copy_raw(4)  # float value
            self.copy_string()  # string value
            audio, field = self.i.string_raw()
            self.o += field
            self.event_audio.append(bool(audio))
            if audio:
                self.copy_raw(8)  # volume, balance

    def animation(self) -> None:
        self.copy_var()  # number of timelines
        self.slot_timelines()
        self.bone_timelines()
        self.ik_timelines()
        self.transform_timelines()
        self.path_timelines()
        self.o += b"\x00"  # physics timelines (new)
        self.deform_timelines()
        self.draw_order()
        self.event_timeline()

    def timelines(self, per_target) -> None:
        """The usual nesting: targets, each with timelines; `per_target` copies one target's timelines."""
        for _ in range(self.copy_var()):
            self.copy_var()  # slot, bone, constraint or skin
            for _ in range(self.copy_var()):
                per_target()

    def curved_frames(self, frames: int, value_bytes: int, curves: int) -> None:
        """Frames of (time, values), each followed by the curve to the next one; a bezier curve has four floats per value."""
        self.copy_raw(4 + value_bytes)
        for _ in range(frames - 1):
            self.copy_raw(4 + value_bytes)
            curve = self.i.u8()
            self.o.append(curve)
            if curve == BEZIER:
                self.copy_raw(16 * curves)

    def slot_timelines(self) -> None:
        def one():
            kind = self.i.u8()
            self.o.append(kind)
            frames = self.copy_var()
            if kind == 0:  # attachment: (time, name) frames
                for _ in range(frames):
                    self.copy_raw(4)
                    self.copy_var()
                return
            if kind not in SLOT_TIMELINES:
                raise SkelError(f"unknown slot timeline type {kind}")
            self.copy_var()  # bezier count
            self.curved_frames(frames, *SLOT_TIMELINES[kind])
        self.timelines(one)

    def bone_timelines(self) -> None:
        def one():
            kind = self.i.u8()
            self.o.append(kind)
            frames = self.copy_var()
            self.copy_var()  # bezier count
            self.curved_frames(frames, *((8, 2) if kind in TWO_VALUES else (4, 1)))
        self.timelines(one)

    def counted_timeline(self, value_bytes: int, curves: int) -> None:
        frames = self.copy_var()
        self.copy_var()  # bezier count
        self.curved_frames(frames, value_bytes, curves)

    def transform_timelines(self) -> None:
        for _ in range(self.copy_var()):
            self.copy_var()  # constraint
            self.counted_timeline(24, 6)

    def path_timelines(self) -> None:
        def one():
            kind = self.i.u8()
            self.o.append(kind)
            self.counted_timeline(*((12, 3) if kind == 2 else (4, 1)))
        self.timelines(one)

    def deform_timelines(self) -> None:
        def attachments():
            for _ in range(self.copy_var()):
                self.copy_var()  # attachment name
                kind = self.i.u8()
                self.o.append(kind)
                frames = self.copy_var()
                if kind != 0:  # sequence frames: time, mode and index, delay
                    self.copy_raw(12 * frames)
                    continue
                self.copy_var()  # bezier count
                self.copy_raw(4)  # first time
                for frame in range(frames):
                    end = self.copy_var()  # how many vertices the frame sets (0: none)
                    if end:
                        self.copy_var()  # first vertex
                        self.copy_raw(4 * end)
                    if frame == frames - 1:
                        break
                    self.copy_raw(4)  # next time
                    curve = self.i.u8()
                    self.o.append(curve)
                    if curve == BEZIER:
                        self.copy_raw(16)
        for _ in range(self.copy_var()):
            self.copy_var()  # skin
            for _ in range(self.copy_var()):
                self.copy_var()  # slot
                attachments()

    def draw_order(self) -> None:
        for _ in range(self.copy_var()):
            self.copy_raw(4)  # time
            for _ in range(self.copy_var()):
                self.copy_var()  # slot
                self.copy_var()  # change

    def event_timeline(self) -> None:
        for _ in range(self.copy_var()):
            self.copy_raw(4)  # time
            index = self.copy_var()
            if index >= len(self.event_audio):
                raise SkelError("an event timeline entry for an event that does not exist")
            self.copy_var()  # int value
            self.copy_raw(4)  # float value
            if self.i.u8():
                self.copy_string()
            else:
                self.o.append(0)  # 4.1 had a boolean for "has its own string"; 4.2 writes a null string for "the event's own"
            if self.event_audio[index]:
                self.copy_raw(8)

    def ik_timelines(self) -> None:
        for _ in range(self.copy_var()):
            self.copy_var()  # constraint
            frames = self.copy_var()
            self.copy_var()  # bezier count
            self.ik_timeline(frames)

    def ik_timeline(self, frames: int) -> None:
        """4.1 stores the three booleans of a frame after its values and the curve to the next frame after that frame's time and values;
        4.2 puts every frame's booleans, its curve type and which of mix / softness follow into one flags byte in front of the frame."""
        i, o = self.i, self.o
        time, mix, soft = i.raw(4), i.raw(4), i.raw(4)
        curve = b""
        frame_list = []
        for frame in range(frames):
            bend, compress, stretch = i.u8(), i.u8(), i.u8()
            frame_list.append((time, mix, soft, bend == 1, compress, stretch, curve))
            if frame == frames - 1:
                break
            time, mix, soft = i.raw(4), i.raw(4), i.raw(4)
            kind = i.u8()
            curve = bytes([IK_STEPPED]) if kind == STEPPED else bytes([IK_BEZIER]) + i.raw(32) if kind == BEZIER else b""
        for time, mix, soft, bend, compress, stretch, curve in frame_list:
            flags = (8 if bend else 0) | (16 if compress else 0) | (32 if stretch else 0) | _implied_one(_f(mix), 1, 2) | (4 if _f(soft) != 0 else 0)
            flags |= curve[0] if curve else 0
            o.append(flags)
            o += time + (mix if flags & 2 else b"") + (soft if flags & 4 else b"") + curve[1:]


# attachment type (the 4.1 type byte, also the low bits of the 4.2 flags) -> the _Transcoder method that reads it
ATTACHMENT_READERS = ("region", "bounding_box", "mesh", "linked_mesh", "path_attachment", "point", "clipping")


def convert_41_to_42(data: bytes) -> bytes:
    """A Spine 4.1 binary skeleton re-encoded as 4.2. Raises SkelError when the file is not 4.1 or is not understood completely."""
    transcoder = _Transcoder(data)
    transcoder.run()
    return bytes(transcoder.o)


def to_current(data: bytes) -> bytes:
    """The skeleton as the game's runtime reads it: 4.1 files are converted, anything else (4.2 already, JSON) is returned unchanged."""
    return convert_41_to_42(data) if (skel_version(data) or "").startswith("4.1") else data


def json_to_current(text: str) -> str:
    """A Spine 4.1 JSON skeleton for the 4.2 runtime: the bone `transform` key is called `inherit` there. Other text is returned unchanged."""
    try:
        doc = json.loads(text)
    except ValueError:
        return text
    if not str((doc.get("skeleton") or {}).get("spine", "")).startswith("4.1"):
        return text
    doc["skeleton"]["spine"] = TARGET_VERSION
    for bone in doc.get("bones", []):
        if "transform" in bone:
            bone["inherit"] = bone.pop("transform")
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
