"""Take one dating scene out of the game's dating bundle as an ordinary mod folder (skeletons, atlases and texture pages), so the
original scene can be looked at in the viewer when no mod of it exists yet. A scene can hold several skeletons
(`illust_dating22_1`, `illust_dating22_2` = its phases), each with its own atlas and pages; they all go in the one folder."""
import os
import re
import warnings
from typing import Callable, Dict, List

import UnityPy

warnings.filterwarnings("ignore")
UnityPy.config.FALLBACK_UNITY_VERSION = os.environ.get("BD2_UNITY_VERSION", "2022.3.22f1")  # set by the manager from game_info; this is only the stand-alone default


def safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', " ", name).strip() or "Dating scene"


def export_scene(bundle_paths: List[str], number: int, out_root: str, title: str, log: Callable[[str], None]) -> List[str]:
    """Write every skeleton of illust_dating<number> into `out_root`/<title>; returns the folder made."""
    wanted = re.compile(rf"^illust_dating{number}(?:_|\.|$)", re.I)
    found: Dict[str, List] = {"skel": [], "atlas": [], "tex": []}
    log("Reading the dating bundle(s) (this can take a minute)...")
    for bundle_path in bundle_paths:
        for obj in UnityPy.load(bundle_path).objects:
            if obj.type.name not in ("TextAsset", "Texture2D"):
                continue
            data = obj.read()
            name = getattr(data, "m_Name", "") or ""
            if not wanted.match(name):
                continue
            if obj.type.name == "Texture2D":
                found["tex"].append((name.lower(), data))
            elif name.lower().endswith(".skel"):
                found["skel"].append((name.lower(), data))
            elif name.lower().endswith(".atlas"):
                found["atlas"].append((name.lower(), data))
    if not found["skel"]:
        raise RuntimeError(f"The dating bundle has no skeleton for illust_dating{number}")
    # One folder for the whole scene: its skeletons are the phases (`illust_dating22_1` = phase 1...), each with its own atlas and
    # pages. Sibling folders would be taken for a multi-mod pack by the scanner, so they cannot be separate mods.
    folder = os.path.join(out_root, safe(title))
    os.makedirs(folder, exist_ok=True)
    for name, data in found["skel"] + found["atlas"]:
        content = data.m_Script
        with open(os.path.join(folder, name), "wb") as f:
            f.write(content.encode("utf-8", "surrogateescape") if isinstance(content, str) else bytes(content))
    for name, data in found["tex"]:
        data.image.save(os.path.join(folder, name + ".png"))
    open(os.path.join(folder, ".normal"), "w").close()
    log(f"Wrote {folder} ({len(found['skel'])} skeleton(s))")
    folders = [folder]
    return folders


if __name__ == "__main__":
    # Run as a helper process (`paths.helper_command`): `dating_scene_export <number> <out_root> <title> <bundle>...`
    import json
    import sys
    done = export_scene(sys.argv[4:], int(sys.argv[1]), sys.argv[2], sys.argv[3], lambda m: print("LOG " + m, flush=True))
    print("RESULT " + json.dumps(done))
