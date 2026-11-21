"""SQLite state store: settings, folder tabs, queue, characters, and the scanned mod index.

One shared connection guarded by a lock (FastAPI runs sync endpoints in a thread pool).
Schema changes go in MIGRATIONS as new entries; PRAGMA user_version tracks the applied count.
"""
import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional

MIGRATIONS = [
    """
    CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE folder_tabs (id TEXT PRIMARY KEY, position INTEGER NOT NULL, data TEXT NOT NULL);
    CREATE TABLE installed_mods (name TEXT PRIMARY KEY, position INTEGER NOT NULL);
    CREATE TABLE templates (tab_id TEXT NOT NULL, name TEXT NOT NULL, mod_names TEXT NOT NULL,
                            PRIMARY KEY (tab_id, name));
    CREATE TABLE queue_items (position INTEGER PRIMARY KEY, data TEXT NOT NULL);
    CREATE TABLE characters (position INTEGER PRIMARY KEY, data TEXT NOT NULL);
    CREATE TABLE mods (
        root TEXT NOT NULL,
        folder_path TEXT NOT NULL,
        mod_key TEXT NOT NULL,
        name TEXT NOT NULL,
        category TEXT,
        character TEXT,
        asset_key TEXT,
        is_multi INTEGER NOT NULL DEFAULT 0,
        data TEXT NOT NULL,
        scanned_at REAL NOT NULL,
        PRIMARY KEY (folder_path, mod_key)
    );
    CREATE INDEX mods_root ON mods (root);
    CREATE INDEX mods_character ON mods (character);
    CREATE INDEX mods_category ON mods (category);
    CREATE INDEX mods_name ON mods (name COLLATE NOCASE);
    """,
]

SORTS = {"name": "name COLLATE NOCASE", "character": "character COLLATE NOCASE, name COLLATE NOCASE",
         "category": "category, name COLLATE NOCASE", "recent": "scanned_at DESC, name COLLATE NOCASE"}


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _like(text: str) -> str:
    return "%" + _escape_like(text) + "%"


class Database:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._migrate()

    def _migrate(self):
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        for number in range(version, len(MIGRATIONS)):
            self._conn.execute("BEGIN")
            try:
                for statement in MIGRATIONS[number].split(";"):
                    if statement.strip():
                        self._conn.execute(statement)
                self._conn.execute(f"PRAGMA user_version={number + 1}")
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def close(self):
        with self._lock:
            self._conn.close()

    def __del__(self):
        try:
            self._conn.close()
        except Exception:
            pass

    def _tx(self):
        return _Transaction(self)

    # --- meta -------------------------------------------------------------
    def get_meta(self, key: str) -> Optional[str]:
        with self._lock:
            row = self._conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str):
        with self._lock:
            self._conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))

    # --- config (same dict shape the old config.json had) -------------------
    def has_config(self) -> bool:
        with self._lock:
            return self._conn.execute("SELECT 1 FROM settings LIMIT 1").fetchone() is not None

    def get_config(self) -> Dict[str, Any]:
        with self._lock:
            cfg = {r["key"]: json.loads(r["value"]) for r in self._conn.execute("SELECT key, value FROM settings")}
            tabs = [json.loads(r["data"]) for r in self._conn.execute("SELECT data FROM folder_tabs ORDER BY position")]
            installed = [r["name"] for r in self._conn.execute("SELECT name FROM installed_mods ORDER BY position")]
            templates: Dict[str, Dict[str, List[str]]] = {}
            for r in self._conn.execute("SELECT tab_id, name, mod_names FROM templates ORDER BY tab_id, name"):
                templates.setdefault(r["tab_id"], {})[r["name"]] = json.loads(r["mod_names"])
        if tabs:
            cfg["folder_tabs"] = tabs
        cfg["installed_mods"] = installed
        cfg["templates"] = templates
        return cfg

    def save_config(self, cfg: Dict[str, Any]):
        """Replace stored config with `cfg`. Keys other than the structured ones go in `settings`."""
        structured = {"folder_tabs", "installed_mods", "templates"}
        with self._tx() as c:
            c.execute("DELETE FROM settings")
            c.executemany("INSERT INTO settings VALUES (?, ?)",
                          [(k, _dumps(v)) for k, v in cfg.items() if k not in structured])
            c.execute("DELETE FROM folder_tabs")
            c.executemany("INSERT OR REPLACE INTO folder_tabs VALUES (?, ?, ?)",
                          [(str(t.get("id", i)), i, _dumps(t)) for i, t in enumerate(cfg.get("folder_tabs") or [])
                           if isinstance(t, dict)])
            c.execute("DELETE FROM installed_mods")
            c.executemany("INSERT OR IGNORE INTO installed_mods VALUES (?, ?)",
                          [(n, i) for i, n in enumerate(cfg.get("installed_mods") or []) if isinstance(n, str)])
            c.execute("DELETE FROM templates")
            c.executemany("INSERT INTO templates VALUES (?, ?, ?)",
                          [(tab, name, _dumps(mods)) for tab, group in (cfg.get("templates") or {}).items()
                           for name, mods in group.items()])

    # --- queue ----------------------------------------------------------------
    def load_queue(self) -> List[dict]:
        with self._lock:
            return [json.loads(r["data"]) for r in self._conn.execute("SELECT data FROM queue_items ORDER BY position")]

    def save_queue(self, items: List[dict]):
        with self._tx() as c:
            c.execute("DELETE FROM queue_items")
            c.executemany("INSERT INTO queue_items VALUES (?, ?)", [(i, _dumps(it)) for i, it in enumerate(items)])

    # --- characters -------------------------------------------------------------
    def load_characters(self) -> Optional[List[dict]]:
        with self._lock:
            rows = self._conn.execute("SELECT data FROM characters ORDER BY position").fetchall()
        return [json.loads(r["data"]) for r in rows] or None

    def save_characters(self, characters: List[dict]):
        with self._tx() as c:
            c.execute("DELETE FROM characters")
            c.executemany("INSERT INTO characters VALUES (?, ?)", [(i, _dumps(ch)) for i, ch in enumerate(characters)])

    # --- mod index ----------------------------------------------------------------
    def replace_mods(self, root: str, mods: List[Dict[str, Any]], scanned_at: float):
        """Make the index for `root` equal to `mods` (one scan's result, already enriched)."""
        rows = []
        for m in mods:
            rows.append((root, m.get("folder_path", ""), str(m.get("id") or m.get("name")), m.get("name", ""),
                         m.get("category"), m.get("character"), m.get("asset_key"), int(bool(m.get("is_multi"))),
                         _dumps(m), scanned_at))
        with self._tx() as c:
            c.execute("DELETE FROM mods WHERE root=?", (root,))
            c.executemany("INSERT OR REPLACE INTO mods VALUES (?,?,?,?,?,?,?,?,?,?)", rows)

    def query_mods(self, q: str = "", character: Optional[str] = None, category: Optional[str] = None,
                   root: Optional[str] = None, sort: str = "name", offset: int = 0, limit: int = 100) -> Dict[str, Any]:
        where, args = [], []
        if q:
            where.append("(name LIKE ? ESCAPE '\\' OR asset_key LIKE ? ESCAPE '\\' OR character LIKE ? ESCAPE '\\')")
            args += [_like(q)] * 3
        for column, value in (("character", character), ("category", category), ("root", root)):
            if value:
                where.append(f"{column}=?")
                args.append(value)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        order = SORTS.get(sort, SORTS["name"])
        limit = max(1, min(int(limit), 1000))
        with self._lock:
            total = self._conn.execute(f"SELECT COUNT(*) FROM mods {clause}", args).fetchone()[0]
            rows = self._conn.execute(f"SELECT data FROM mods {clause} ORDER BY {order} LIMIT ? OFFSET ?",
                                      args + [limit, max(0, int(offset))]).fetchall()
        return {"total": total, "offset": max(0, int(offset)), "limit": limit,
                "mods": [json.loads(r["data"]) for r in rows]}

    INDEX_FIELDS = ("id", "name", "folder_name", "folder_path", "character", "category", "asset_key", "asset_keys", "asset_stem",
                    "is_multi", "has_backup", "has_json_anim", "texture_count", "files")

    def index_rows(self, root: Optional[str] = None) -> List[Dict[str, Any]]:
        """Every indexed mod, trimmed to what the library list needs (no duplicated per-type file lists)."""
        query, args = "SELECT root, data FROM mods", []
        if root:
            query, args = query + " WHERE root=?", [root]
        with self._lock:
            rows = self._conn.execute(query + " ORDER BY name COLLATE NOCASE", args).fetchall()
        result = []
        for row in rows:
            full = json.loads(row["data"])
            trimmed = {key: full[key] for key in self.INDEX_FIELDS if key in full}
            trimmed["root"] = row["root"]
            result.append(trimmed)
        return result

    def mods_by_names(self, names: List[str]) -> List[Dict[str, Any]]:
        """Indexed mods whose name is in `names` (e.g. the installed list), in chunks to respect SQLite's variable limit."""
        found: List[Dict[str, Any]] = []
        unique = list(dict.fromkeys(names))
        with self._lock:
            for start in range(0, len(unique), 500):
                chunk = unique[start:start + 500]
                marks = ",".join("?" * len(chunk))
                found += [json.loads(r["data"]) for r in
                          self._conn.execute(f"SELECT data FROM mods WHERE name IN ({marks}) ORDER BY name", chunk)]
        return found

    def mods_by_folders(self, folder_paths: List[str]) -> List[Dict[str, Any]]:
        """Indexed mods living in exactly these folders, in chunks to respect SQLite's variable limit."""
        found: List[Dict[str, Any]] = []
        unique = list(dict.fromkeys(folder_paths))
        with self._lock:
            for start in range(0, len(unique), 500):
                chunk = unique[start:start + 500]
                marks = ",".join("?" * len(chunk))
                found += [json.loads(r["data"]) for r in
                          self._conn.execute(f"SELECT data FROM mods WHERE folder_path IN ({marks})", chunk)]
        return found

    def remove_folders(self, folder_paths: List[str]):
        """Drop index rows for deleted mod folders (and anything nested inside them)."""
        with self._tx() as c:
            for path in folder_paths:
                c.execute("DELETE FROM mods WHERE folder_path=? OR folder_path LIKE ? ESCAPE '\\'",
                          (path, _escape_like(path.rstrip("/\\") + os.sep) + "%"))

    def prune_roots(self, keep_roots: List[str]) -> int:
        """Forget indexed mods whose scan root is no longer a configured folder (all of them when no folder is left)."""
        if not keep_roots:
            with self._tx() as c:
                return c.execute("DELETE FROM mods").rowcount
        marks = ",".join("?" * len(keep_roots))
        with self._tx() as c:
            return c.execute(f"DELETE FROM mods WHERE root NOT IN ({marks})", keep_roots).rowcount

    def has_folder(self, folder_path: str) -> bool:
        with self._lock:
            return self._conn.execute("SELECT 1 FROM mods WHERE folder_path=? LIMIT 1", (folder_path,)).fetchone() is not None

    def mod_facets(self) -> Dict[str, Dict[str, int]]:
        with self._lock:
            return {col: {(r[0] or ""): r[1] for r in
                          self._conn.execute(f"SELECT {col}, COUNT(*) FROM mods GROUP BY {col}")}
                    for col in ("character", "category", "root")}


class _Transaction:
    def __init__(self, db: Database):
        self.db = db

    def __enter__(self):
        self.db._lock.acquire()
        self.db._conn.execute("BEGIN")
        return self.db._conn

    def __exit__(self, exc_type, exc, tb):
        try:
            self.db._conn.execute("ROLLBACK" if exc_type else "COMMIT")
        finally:
            self.db._lock.release()
        return False


def _read_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def import_legacy_json(db: Database, config_path: str, queue_path: str, characters_path: str) -> List[str]:
    """One-time import of config.json / queue_state.json / characters.json. Files are left untouched."""
    if db.get_meta("legacy_json_imported"):
        return []
    imported = []
    cfg = _read_json(config_path)
    if isinstance(cfg, dict) and cfg:
        db.save_config(cfg)
        imported.append("config")
    queue = _read_json(queue_path)
    if isinstance(queue, dict):
        queue = queue.get("queue")
    if isinstance(queue, list):
        db.save_queue([i for i in queue if isinstance(i, dict)])
        imported.append("queue")
    characters = _read_json(characters_path)
    if isinstance(characters, list) and characters:
        db.save_characters([c for c in characters if isinstance(c, dict)])
        imported.append("characters")
    db.set_meta("legacy_json_imported", ",".join(imported) or "none")
    return imported
