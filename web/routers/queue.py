from pydantic import BaseModel
from typing import List
from fastapi import APIRouter
from web.state import load_queue_state, manager, save_queue_state

router = APIRouter()


@router.get("/api/queue/state")
def get_queue_state():
    raw_items = load_queue_state()
    validated, issues = manager.validate_queue_items(raw_items)
    return {"status": "ok", "queue": validated, "issues": issues}


class SaveQueueRequest(BaseModel):
    queue: List[dict]


@router.post("/api/queue/state")
def save_queue_state_endpoint(req: SaveQueueRequest):
    sanitized = []
    for j in req.queue:
        clean = {k: v for k, v in j.items() if k not in ("abortController",)}
        sanitized.append(clean)
    ok = save_queue_state(sanitized)
    return {"status": "ok" if ok else "error", "count": len(sanitized)}


@router.post("/api/queue/validate")
def validate_queue_endpoint(req: SaveQueueRequest):
    validated, issues = manager.validate_queue_items(req.queue)
    return {"status": "ok", "queue": validated, "issues": issues}
