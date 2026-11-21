"""Skeleton files as the Spine 4.2 runtime wants them: what the preview serves and what the health check reads (the format work is in
skel_convert.py). Converted files are kept per file version, so previewing and checking one file converts it once."""
import hashlib
import os

import skel_convert


def _cached_path(path: str, cache_dir: str) -> str:
    st = os.stat(path)
    key = f"{os.path.realpath(path)}|{st.st_size}|{st.st_mtime_ns}|{skel_convert.REVISION}"
    return os.path.join(cache_dir, hashlib.sha1(key.encode("utf-8")).hexdigest() + ".skel")


def current_bytes(path: str, cache_dir: str | None = None) -> bytes | None:
    """The 4.2 content of a skeleton file, or None when it needs no conversion (4.2 already, anything that is not a 4.1 skeleton).
    A 4.1 skeleton that cannot be read to the end raises skel_convert.SkelError."""
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
        converted = skel_convert.json_to_current(text)
        return converted.encode("utf-8") if converted != text else None
    cached = _cached_path(path, cache_dir) if cache_dir else None
    if cached and os.path.isfile(cached):
        with open(cached, "rb") as f:
            return f.read()
    with open(path, "rb") as f:
        if not (skel_convert.skel_version(f.read(64)) or "").startswith("4.1"):
            return None
        f.seek(0)
        converted = skel_convert.convert_41_to_42(f.read())
    if cached:
        os.makedirs(cache_dir, exist_ok=True)
        with open(cached + ".tmp", "wb") as f:
            f.write(converted)
        os.replace(cached + ".tmp", cached)
    return converted
