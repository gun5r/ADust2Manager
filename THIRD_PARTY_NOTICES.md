# Third-party notices

ADust2Manager itself is MIT licensed (see `LICENSE`). It contains code taken or adapted from other MIT projects, uses a few
third-party components, and talks to a game it has no connection with. Their notices follow.

## Spine skeleton formats

`core/skel_convert.py` (4.1 to 4.2 binary skeletons) was written for this project. It follows the binary layouts that Esoteric Software's
Spine runtimes read (`SkeletonBinary` of the 4.1 and 4.2 branches); no runtime code is included. Spine and its runtimes belong to Esoteric
Software LLC; see the Spine Runtimes License (https://esotericsoftware.com/spine-runtimes-license) and the note on the Spine web player in the README.

## Code copied or adapted from other projects (MIT)

**BDroid_X** (https://github.com/Ark-Repoleved/BDroid_X). These files are copies or close derivatives of its Python sources, and
the repacking, resolving and merging logic of the manager was ported from it:
`core/repacker/repacker.py` and `core/utils/atlas_operations.py`, and the thread lock added to `core/repacker/json_to_skel.py`, with `core/resolver.py`, `core/spine_merger.py` and
`core/catalog_indexer.py` rewritten from the same design.

```
MIT License

Copyright (c) 2026 Ark Repoleved.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**ReDustX** (https://github.com/Jelosus2/ReDustX) and **BD2-L2D-Viewer** (https://github.com/Jelosus2/BD2-L2D-Viewer): `core/repacker/json_to_skel.py` and `core/maintenance_info_pb2.py` are copies of ReDustX's files (the first with a thread lock added
by BDroid_X), and the catalog
and bundle-resolution logic (`core/catalog_parser.py`, `core/catalog_indexer.py`, `core/resolver.py`) is adapted from ReDustX, and the
viewer's framing, cutscene chaining and layer handling follow ideas of BD2-L2D-Viewer. Both have the same notice:

```
MIT License

Copyright (c) 2025 Jelosus2

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Components used as downloaded, not part of this repository

**Spine Runtimes** (the web player, stored in the data folder's `libs`). Copyright (c) 2013-2023 Esoteric Software LLC, under the Spine Runtimes
License (https://esotericsoftware.com/spine-runtimes-license), which is NOT an open-source licence: software built on the runtimes
may be distributed only if each user holds a Spine Editor licence (see section 2 of the Spine Editor License Agreement for the
alternative). The runtime is neither stored in this repository nor included in the releases: `core/spine_player.py` downloads it on the user's
computer from the npm package `@esotericsoftware/spine-player` (version and checksum pinned) together with its licence text
(`SPINE-RUNTIMES-LICENSE.txt`), after applying three small patches of ours (marked `ADust2Manager` in the file). Anyone who runs
the manager is responsible for holding the Spine licence their use requires.

**PyInstaller** (the tool that builds the Windows and Linux programs; its bootloader is part of them): GPL-2.0-or-later with the
special exception that permits distributing programs built with it under any licence (https://pyinstaller.org). The programs also
contain Python and the packages of `requirements.txt` under their own licences. UnityPy imports `fmod_toolkit` only to convert audio,
which the manager never does; the packaged program contains an empty stand-in (`packaging/stubs`) instead of that package, so FMOD's
proprietary library is not redistributed.

**astcenc** (`bin/astcenc`; the Windows build downloads the same version's `astcenc-avx2.exe`): Copyright (c) 2011-2026 Arm Limited, Apache License 2.0, full text in `bin/ASTCENC-LICENSE.txt`.
Source: https://github.com/ARM-software/astc-encoder.

**Python packages** (installed from `requirements.txt`, not included): fastapi (MIT), uvicorn (BSD-3-Clause), Pillow (MIT-CMU),
UnityPy (MIT), requests (Apache-2.0), beautifulsoup4 (MIT), protobuf (BSD-3-Clause), tqdm (MPL-2.0 and MIT). PySide6, if you use
the desktop mascots, is LGPL-3.0 and is not included either.

**Fonts** (installed from npm, bundled into the built UI): Plus Jakarta Sans and JetBrains Mono through `@fontsource`, SIL Open
Font License 1.1; the licence texts are in those packages.

**Lucide icons** (`frontend/src/ui/icons.ts`, generated from `lucide-static`):

```
ISC License

Copyright (c) 2026 Lucide Icons and Contributors

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
```

Some of the icons used (check, x, arrow-left, arrow-right, search, loader, trash-2, download, corner arrows) derive from Feather:

```
MIT License

Copyright (c) 2013-present Cole Bemis

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## The game

Brown Dust 2 and its characters, art, sounds and data belong to Neowiz and their licensors. This project is an independent fan
tool: it is not affiliated with, endorsed by or sponsored by Neowiz. No game content is included in this repository. Everything
derived from the game (touch rules, sound names, costume portraits, original bundles) is downloaded by the user's own copy of the
program from the game's servers or read from the user's own game files. Mods are the work of their authors and are never
distributed with the manager.
