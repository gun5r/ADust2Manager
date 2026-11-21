import asyncio
import os
import sys
import threading
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from web import state
from web.state import (STATIC_DIR, DEFAULT_PORT, configured_quality, db, manager, character_manager, ws_manager, emit_log,
                       load_config, save_config, load_queue_state, save_queue_state)
from web.routers import activity, cache, dating_audio, dmascot, install, library, multi, queue, settings, spine, tools, portraits, skeleton
from web.routers.multi import PrepareMultiSelectionRequest, prepare_multi_selections_endpoint
from dmascot_manager import dmascot_mgr
from paths import FRONTEND_DIST, LIBS_DIR

LOCAL_ORIGIN = r"https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?"

app = FastAPI(title="ADust2Manager")

app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    # Only pages served from this machine may call the API; a website you visit must not be able to
    # delete mod folders or push bundles through it.
    allow_origin_regex=LOCAL_ORIGIN,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    elif request.url.path.startswith("/api/mod-assets/"):
        # Stored by the browser but revalidated on every use (ETag/Last-Modified come with FileResponse): re-opening a mod
        # or pre-loading its textures is cheap, and a merged or edited texture is never served stale.
        response.headers["Cache-Control"] = "no-cache"
    return response

os.makedirs(LIBS_DIR, exist_ok=True)
app.mount("/static/libs", StaticFiles(directory=LIBS_DIR), name="libs")  # the Spine player, in the data folder
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Svelte UI (frontend/): built with `npm run build`; its page is served at / and its assets under /app.
NEW_UI_INDEX = os.path.join(FRONTEND_DIST, "index.html")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/app", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

for module in (activity, settings, cache, queue, library, install, spine, multi, dmascot, dating_audio, tools, portraits, skeleton):
    app.include_router(module.router)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

@app.get("/")
def get_index():
    if os.path.exists(NEW_UI_INDEX):
        return FileResponse(NEW_UI_INDEX)
    return HTMLResponse(
        "<h1>ADust2Manager</h1><p>The interface is not built yet. Run "
        "<code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code> and reload.</p>",
        status_code=503,
    )

@app.get("/api/ping")
def ping():
    """Lets a second launch tell that this port is already served by the manager."""
    return {"app": "ADust2Manager"}


@app.post("/api/quit")
def quit_app(request: Request):
    """Stop the server (the packaged program has no window to close). The custom header makes a web page of another origin need a CORS preflight, which is refused."""
    if request.headers.get("x-adust2") != "1":
        raise HTTPException(status_code=403, detail="Missing header")
    request_quit()
    return {"status": "stopping"}


def request_quit():
    """Stop the server. Should it not have ended within 10 seconds (a stuck thread), the process ends anyway: quitting never leaves
    a program running in the background without its icon."""
    if state.server is not None:
        state.server.should_exit = True
    timer = threading.Timer(10, os._exit, args=(0,))
    timer.daemon = True
    timer.start()


def _warm_up_index():
    """Load (the first time: download and build) the game's asset index in the background, so the first mod a user queues does not wait for it."""
    with state.track("Preparing the game's asset index", "setup") as t:
        try:
            t.log("Preparing the game's asset index (the first time this downloads the game catalog, about 70 MB)...")
            if manager.get_or_load_index(configured_quality(), t.log):
                t.log("The game's asset index is ready.", "success")
        except Exception as e:
            t.log(f"Could not prepare the game's asset index now: {e}", "warning")
            t.fail(str(e))


@app.on_event("startup")
async def startup_event():
    state.loop = asyncio.get_running_loop()
    threading.Thread(target=_warm_up_index, name="asset-index-warm-up", daemon=True).start()
    try:
        raw_q = load_queue_state()
        if raw_q:
            validated_q, issues = manager.validate_queue_items(raw_q)
            save_queue_state(validated_q)
            print(f"[Queue Persistent State] Loaded {len(validated_q)} mods from disk ({len(issues)} issues found).")
            for iss in issues:
                print(f"  ⚠️ [Queue Warning] {iss.get('mod_name')}: {iss.get('issue')}")
    except Exception as e:
        print(f"[Queue Startup Check Error]: {e}")

def run_server(port: Optional[int] = None):
    import uvicorn
    chosen_port = port or DEFAULT_PORT
    state.CURRENT_PORT = chosen_port
    dmascot_mgr.port = chosen_port

    print("=" * 60)
    print(f"  ADust2Manager running at:")
    print(f"  👉 http://127.0.0.1:{chosen_port}")
    print("=" * 60)
    config = uvicorn.Config(app, host="127.0.0.1", port=chosen_port, log_level="info")
    if sys.platform == "win32":  # the default Windows loop (Proactor) logs "AssertionError" noise when a browser connection closes mid-write
        import asyncio
        config.get_loop_factory = lambda: asyncio.SelectorEventLoop
    state.server = uvicorn.Server(config)
    state.server.run()

if __name__ == "__main__":
    p = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    run_server(p)
