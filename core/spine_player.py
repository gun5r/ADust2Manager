"""The Spine web player, fetched on first start.

The runtime belongs to Esoteric Software under the Spine Runtimes License (https://esotericsoftware.com/spine-runtimes-license), which
is not MIT and requires every user of software built on it to hold a Spine Editor license, so it is not part of this project or its
releases: this downloads the pinned npm package onto the user's own computer, applies three small patches of ours and stores its
LICENSE next to it.
"""
import base64
import hashlib
import io
import os
import tarfile
from typing import Callable

import requests

VERSION = "4.2.120"  # the game's skeletons are 4.2 (4.2.43 as of Nov 2026); any 4.2.x runtime reads them
URL = f"https://registry.npmjs.org/@esotericsoftware/spine-player/-/spine-player-{VERSION}.tgz"
INTEGRITY = "sha512-N3LVJp0DkyK/h4AntTDedwDqLxrWYK9gedi0qWcrstgu/h7RYfdrXviza8qKt11v5dlyWpZACWbXLGicWbqfFA=="  # npm's checksum of that tarball
FILES = {"package/dist/iife/spine-player.js": "spine-player.js", "package/dist/spine-player.css": "spine-player.css",
         "package/LICENSE": "SPINE-RUNTIMES-LICENSE.txt"}

# Straight-alpha textures: premultiply them on upload (no dark outline along mesh edges) and draw multiply slots right.
PATCHES = [
    ("      if (_GLTexture.DISABLE_UNPACK_PREMULTIPLIED_ALPHA_WEBGL) gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);",
     "      // ADust2Manager: straight-alpha textures are premultiplied on upload so bilinear filtering never mixes in the black RGB of transparent texels (a dark outline along every mesh edge)\n      gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, !!_GLTexture.PREMULTIPLY_ON_UPLOAD);"),
    ("gl_FragColor.rgb = ((texColor.a - 1.0) * v_dark.a + 1.0 - texColor.rgb) * v_dark.rgb + texColor.rgb * v_light.rgb;",
     "gl_FragColor.rgb = ((texColor.a - 1.0) * v_dark.a + 1.0 - texColor.rgb) * v_dark.rgb + texColor.rgb * v_light.rgb;\n\t\t\t\t\t// ADust2Manager: a negative dark alpha marks a multiply slot on straight-alpha textures, which must be premultiplied for the multiply blend\n\t\t\t\t\tif (v_dark.a < 0.0) gl_FragColor.rgb = texColor.rgb * texColor.a * v_light.rgb;"),
    ("          let slotBlendMode = slot.data.blendMode;\n",
     "          let slotBlendMode = slot.data.blendMode;\n          // ADust2Manager: multiply blending is only right with premultiplied textures; flag straight-alpha ones for the shader (see the fragment shader)\n          if (!premultipliedAlpha && slotBlendMode == 2 && !slot.darkColor)\n            darkColor.a = -1;\n"),
]


def ensure(libs_dir: str, log: Callable[[str], None] = print) -> bool:
    """Make sure libs_dir holds the patched player; True when it does (False: no internet and nothing there yet)."""
    marker = os.path.join(libs_dir, ".version")
    if all(os.path.isfile(os.path.join(libs_dir, n)) for n in FILES.values()) and _read(marker) == VERSION:
        return True
    try:
        log(f"Fetching the Spine web player {VERSION} (needed once)...")
        data = requests.get(URL, timeout=60).content
        if "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode() != INTEGRITY:
            raise RuntimeError("the download does not match its checksum")
        out = {}
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for member, name in FILES.items():
                out[name] = tar.extractfile(member).read()
        js = out["spine-player.js"].decode("utf-8")
        for old, new in PATCHES:
            if js.count(old) != 1:
                raise RuntimeError("the Spine player no longer matches the patches")
            js = js.replace(old, new)
        out["spine-player.js"] = js.encode("utf-8")
        os.makedirs(libs_dir, exist_ok=True)
        for name, content in out.items():
            with open(os.path.join(libs_dir, name), "wb") as f:
                f.write(content)
        with open(marker, "w") as f:
            f.write(VERSION)
        return True
    except Exception as e:
        log(f"Could not fetch the Spine web player: {e}. The previews need it; start again with an internet connection.")
        return False


def _read(path: str) -> str:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""
