"""Arsenal Fan 360 API routes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .. import store, genie, db

router = APIRouter()


@router.get("/overview")
def overview():
    return store.overview()


@router.get("/supporters")
def supporters(q: str = "", limit: int = 25):
    return store.search(q, limit)


@router.get("/supporter/{sid}")
def supporter(sid: str):
    d = store.detail(sid)
    if not d:
        raise HTTPException(404, "supporter not found")
    return d


@router.get("/opportunities")
def opportunities():
    return store.opportunities()


@router.get("/opportunities/{otype}/supporters")
def opportunity_supporters(otype: str):
    return store.opportunity_supporters(otype)


class ActivationReq(BaseModel):
    supporter_id: str
    recommended_action: str
    selected_action: str
    campaign: str


@router.post("/activation")
def activation(req: ActivationReq):
    return db.write_activation(req.supporter_id, req.recommended_action, req.selected_action, req.campaign)


@router.get("/activations")
def activations():
    return db.recent_activations()


@router.get("/genie/suggestions")
def genie_suggestions():
    return {"questions": genie.SUGGESTIONS}


class AskReq(BaseModel):
    question: str


@router.post("/genie/ask")
def genie_ask(req: AskReq):
    return genie.ask(req.question)
