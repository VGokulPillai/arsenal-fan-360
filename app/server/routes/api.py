"""Arsenal Fan 360 API routes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .. import store, genie, db, copilot

router = APIRouter()


@router.get("/overview")
def overview():
    return store.overview()


@router.get("/executive")
def executive():
    """Commercial command-centre metrics + illustrative business case (CCO / Head of Fan Engagement)."""
    return store.executive()


@router.get("/campaign-brief/{sid}")
def campaign_brief(sid: str):
    """AI Campaign Copilot: grounded, human-reviewable campaign brief for a supporter."""
    b = copilot.brief(sid)
    if b.get("error"):
        raise HTTPException(404, b["error"])
    return b


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
    next_best_action: str
    campaign_objective: str = ""
    recommended_channel: str = ""
    campaign_message: str = ""
    approved_by_user: str = "marketing_user"


@router.post("/activation")
def activation(req: ActivationReq):
    return db.write_activation(
        req.supporter_id, req.next_best_action, req.campaign_objective,
        req.recommended_channel, req.campaign_message, req.approved_by_user)


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
