"""The dating scenes' tool icons (hand, brush, ...) cut out of the game's InteractionGUI sprite atlas.

The atlas bundle holds one packed image and, per sprite, a name and a rectangle. Unity keeps the rectangles in a dictionary keyed by
the sprite's asset id, which is not in this bundle, so the entries are paired with the names BY ORDER (checked by eye: the glove is
icon_interaction_toolbar_1, 22 and 23 sit next to their *_censorship variants, summer scenes get the beach ball and ice cream).
"""
import os
import warnings
from typing import List

from game_info import UNITY_VERSION


def extract_tool_icons(bundle_path: str, out_dir: str) -> List[str]:
    """Write every sprite of the atlas as <name>.png into out_dir; returns the names written."""
    import UnityPy
    UnityPy.config.FALLBACK_UNITY_VERSION = UNITY_VERSION
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        env = UnityPy.load(bundle_path)
        texture = next(o.read() for o in env.objects if o.type.name == "Texture2D")
        atlas = next(o.read() for o in env.objects if o.type.name == "SpriteAtlas")
        image = texture.image
    height = image.size[1]
    names = list(atlas.m_PackedSpriteNamesToIndex)
    boxes = [data for _key, data in atlas.m_RenderDataMap]
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for name, data in zip(names, boxes):
        rect = data.textureRect
        x, y, w, h = (int(round(v)) for v in (rect.x, rect.y, rect.width, rect.height))
        image.crop((x, height - y - h, x + w, height - y)).save(os.path.join(out_dir, f"{name}.png"))  # Unity's origin is bottom left
        written.append(name)
    return written
