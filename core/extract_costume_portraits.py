#!/usr/bin/env python3
"""Extract the costume portraits (illust_inven_char<costume>_<n>) of the game's IllustInventory bundle as PNG files named
<costume>.png. Run as a helper process (`paths.helper_command`):
    venv/bin/python -I core/extract_costume_portraits.py bundle out_dir
"""
import os
import re
import sys
import warnings

warnings.filterwarnings("ignore")
import UnityPy

UnityPy.config.FALLBACK_UNITY_VERSION = os.environ.get("BD2_UNITY_VERSION", "2022.3.22f1")  # set by the manager from game_info; this is only the stand-alone default

if __name__ == "__main__":
    bundle, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    count = 0
    for obj in UnityPy.load(bundle).objects:
        if obj.type.name != "Texture2D":
            continue
        texture = obj.read()
        match = re.fullmatch(r"illust_inven_char(\d+)_\d+", texture.m_Name)
        if match:
            texture.image.save(os.path.join(out, f"{match.group(1)}.png"))
            count += 1
    print(count)
