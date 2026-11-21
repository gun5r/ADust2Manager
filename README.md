# ADust2Manager

A mod manager for **Brown Dust 2** on Android that does the heavy work on your PC. It repacks the game files with your mods (texture compression, skeleton conversion) and sends the result to your phone over ADB. The interface is a local web page, so there is nothing to install besides the program itself.

> Independent fan tool, not affiliated with or endorsed by Neowiz. No game content is included: the program builds what it needs on your computer from the game's own servers.

## Features

- **Library**: your mods sorted by character, costume and category, with portraits, search, filters, folder tabs and duplicate detection. Built for thousands of mods.
- **Live preview**: check a mod animated in the browser before installing it.
- **Interactive mode**: try the touch-driven scenes with their sounds, a step-by-step guide and phase navigation.
- **Batch queue**: prepare and install many mods at once with live progress.
- **Conflict resolver**: finds mods that replace the same game file and lets you choose what gets installed.
- **Spine 4.2 ready**: converts mods made for older Spine versions, on the fly or for a whole library at once.
- **Damaged file warning**: flags mods with incomplete downloads instead of just showing them broken.
- **Safe installs**: the original game file on the phone is backed up before it is replaced, and can be restored at any time.
- **Portable**: everything stays in the program's folder; deleting it removes it all.

## Quick start

1. Download the program for your system from the [Releases](../../releases) page (`ADust2Manager-windows-x64.zip` or `ADust2Manager-linux-x64.tar.gz`) and unpack it anywhere you can write to (not `Program Files`).
2. Double-click `ADust2Manager`. Your browser opens the manager. The first start downloads a few components, so it needs internet.
3. The first time, open **Settings / Tools > Initial Setup**. It prepares everything the manager needs and guides you through the rest.
4. Put your mods in the `Mods` folder next to the program, or add other folders as tabs.
5. Connect your phone (USB debugging on, game installed), pick mods, queue them and install.

On Windows, SmartScreen may warn that the program is unsigned; choose *More info > Run anyway*.

### Mod folders

A mod is a folder with the files the game replaces: textures (`.png`), an atlas (`.atlas`) and a skeleton (`.skel`, or `.json`, which is converted).

```text
Mods/
  My Mod/
    texture.png
    skeleton.atlas
    skeleton.skel
```

### Running from source

You need **Python 3.12+** and **Node.js 22+**.

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt     # Windows: .venv\Scripts\python.exe
cd frontend && npm ci && npm run build && cd ..
.venv/bin/python run.py                                  # optional: a port number, default 8082
```

On Windows run `python packaging/fetch_astcenc.py` once to get the texture encoder.

## Known limits

- Android only, through ADB. There is no iOS or macOS version.
- A few interactive scenes are stored by the game in several separate parts and cannot be installed as one mod yet.
- Modifying game files can go against the game's terms of service. Use it at your own risk.

## Troubleshooting

- **No phone listed**: open Settings / Tools > Troubleshooting, which checks the connection. Check the cable, USB debugging and the prompt on the phone.
- **A preview looks wrong**: the same page lists the usual fixes.
- **Interactive mode has no data**: run Initial Setup again.
- **Logs**: the console panel in the manager, and `data/manager.log` next to the program.

## Credits

This project would not exist without the work of the Brown Dust 2 modding community. Thank you to everyone who reverse-engineered the game's formats, built the tools and viewers that came before this one, and shared what they learned, in particular:

- **Ark-Repoleved**, creator of [BDroid_X](https://github.com/Ark-Repoleved/BDroid_X)
- **Jelosus1 / Jelosus2**, creator of [ReDustX](https://github.com/Jelosus2/ReDustX) and [BD2-L2D-Viewer](https://github.com/Jelosus2/BD2-L2D-Viewer)
- **Synae**, creator of BrownDustX
- The **BrownDust2 Modding Community** ([browndust2modding.pages.dev](https://browndust2modding.pages.dev/characters))

## License

The code of this project is MIT licensed, see [LICENSE](LICENSE). It contains code from other MIT projects and uses third-party components; their notices are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

**Spine runtime:** the web player is Esoteric Software's and is not MIT. It is not stored in this repository or in the releases: the manager downloads it on first start from the `@esotericsoftware/spine-player` package under the [Spine Runtimes License](https://esotericsoftware.com/spine-runtimes-license), which requires each user of software built on it to hold a Spine Editor license.

**Brown Dust 2:** the game, its art, sounds and data belong to Neowiz and their licensors. None of it is included here.
