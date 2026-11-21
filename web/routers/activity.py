"""What the program is doing (see core/activity.py). The pages get it live over /ws; these endpoints serve the same on demand, let the
user dismiss a failure, and let the browser report work that only runs there (rendering portraits)."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from web.state import hub

router = APIRouter()


@router.get("/api/activity")
def activity(logs: int = 600):
    return {**hub.snapshot(), "logs": hub.history(logs)}


@router.post("/api/activity/acknowledge")
def acknowledge():
    """The user has seen the failure: the light goes back to standby."""
    hub.acknowledge()
    return {"status": "ok"}


class BrowserTask(BaseModel):
    id: Optional[int] = None
    title: str = ""
    detail: str = ""
    progress: Optional[float] = None
    state: str = "running"  # running | done | error | cancelled
    error: str = ""


@router.post("/api/activity/report")
def report(req: BrowserTask):
    """A task the browser runs reports in: no id starts one (the id comes back), then updates, then a final state."""
    if req.id is None:
        return {"id": hub.start(req.title or "Working", "browser")["id"]}
    task = hub.tasks.get(req.id)
    if not task:
        raise HTTPException(status_code=404, detail="Unknown task")
    with hub.lock:
        if req.detail:
            task["detail"] = req.detail
        if req.progress is not None:
            task["progress"] = max(0.0, min(1.0, req.progress))
        task["updated"] = __import__("time").time()
    if req.state != "running":
        hub.finish(req.id, req.state, req.error)
    else:
        hub._publish(False)
    return {"id": req.id}
