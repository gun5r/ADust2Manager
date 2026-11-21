"""The few facts about the game itself that code needs, in one place (the game's Android package and the Unity version it was built with).
BD2_UNITY_VERSION overrides the version when a game update moves to another Unity."""
import os

PACKAGE_NAME = "com.neowizgames.game.browndust2"
UNITY_VERSION = os.environ.get("BD2_UNITY_VERSION", "2022.3.22f1")
# What the game's own web requests (maintenance info, catalog) send as user agent
UNITY_USER_AGENT = f"UnityPlayer/{UNITY_VERSION} (UnityWebRequest/1.0, libcurl/8.5.0-DEV)"
