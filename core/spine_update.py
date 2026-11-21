"""Update every mod skeleton in the library from Spine 4.1 to 4.2 (see skel_convert). The originals are kept next to the mods in `.spine41/`."""
import os
import shutil
from typing import Callable, Iterator

import skel_convert
from mod_assets import is_mod_folder

BACKUP_DIR = ".spine41"
SKELETON = (".skel", ".skel.bytes")
Log = Callable[[str, str], None]


def _no_log(message: str, level: str = "info") -> None:
    pass


def iter_skeletons(roots: list) -> Iterator[str]:
    """Binary skeletons below the mod folders (the folders the scanner skips are skipped here too)."""
    for root in roots:
        for folder, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if is_mod_folder(d)]
            for name in files:
                if name.lower().endswith(SKELETON) and not name.startswith("."):
                    yield os.path.join(folder, name)


def version_of(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return skel_convert.skel_version(f.read(64)) or ""
    except OSError:
        return ""


def survey(roots: list, log: Log = _no_log) -> list:
    """[(path, version)] of every skeleton in the library: the one slow pass (walking a big library and reading each header), shared by
    the check and the update. The total is known before the headers are read, so the progress can say how far it is."""
    log("Looking through the mod folders for skeletons…", "info")
    paths = list(iter_skeletons(roots))
    rows = []
    for k, path in enumerate(paths, 1):
        if k % 50 == 0:
            log(f"Checked {k} of {len(paths)} skeletons…", "info")
        rows.append((path, version_of(path)))
    return rows


def counts_of(rows: list) -> dict:
    """How many skeletons are 4.1 (to update), 4.2 (fine already) or something else, and in how many mod folders the 4.1 ones are."""
    v41 = [p for p, v in rows if v.startswith("4.1")]
    return {"total": len(rows), "v41": len(v41), "v42": sum(v.startswith("4.2") for _, v in rows),
            "other": sum(not v.startswith(("4.1", "4.2")) for _, v in rows), "folders": len({os.path.dirname(p) for p in v41})}


def scan(roots: list, log: Log = _no_log) -> dict:
    return counts_of(survey(roots, log))


def convert_in_place(path: str) -> None:
    """Replace one 4.1 skeleton by its 4.2 version. The file being converted is the newest original there is, so it replaces any earlier
    backup (a mod downloaded again keeps the backup of what is being replaced now, not of a file that is long gone)."""
    with open(path, "rb") as f:
        converted = skel_convert.convert_41_to_42(f.read())
    backup_dir = os.path.join(os.path.dirname(path), BACKUP_DIR)
    os.makedirs(backup_dir, exist_ok=True)
    shutil.copy2(path, os.path.join(backup_dir, os.path.basename(path)))
    tmp = path + ".tmp42"
    with open(tmp, "wb") as f:
        f.write(converted)
    shutil.copystat(path, tmp)
    os.replace(tmp, path)


def update(roots: list, log: Log = _no_log) -> dict:
    """Convert every 4.1 skeleton in place. Damaged files are left alone and listed. `counts` is what a new check would say afterwards."""
    rows = survey(roots, log)
    todo = [p for p, v in rows if v.startswith("4.1")]
    done, failed = set(), []
    for k, path in enumerate(todo, 1):
        try:
            convert_in_place(path)
            done.add(path)
        except (skel_convert.SkelError, OSError) as e:
            failed.append({"file": path, "error": str(e)})
        if k % 25 == 0 or k == len(todo):
            log(f"Updated {len(done)} of {len(todo)} skeletons to Spine 4.2" + (f", {len(failed)} could not be read" if failed else ""), "info")
    after = [(p, skel_convert.TARGET_VERSION if p in done else v) for p, v in rows]
    return {"checked": len(todo), "updated": len(done), "failed": failed, "counts": counts_of(after)}
