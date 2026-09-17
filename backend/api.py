"""HTTP API for the Human-in-the-Loop approval queue."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import approvals
from agent.core import resume_approval


app = FastAPI(title="AgentHive Logistics API", version="1.0.0")


class ReviewRequest(BaseModel):
    reviewer: str = "operations-agent"
    comment: str | None = None


@app.get("/approvals")
def get_approvals():
    return {"approvals": approvals.list_all()}


@app.get("/approvals/{approval_id}")
def get_approval(approval_id: str):
    approval = approvals.get(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request was not found")
    return approval


@app.post("/approvals/{approval_id}/approve")
def approve_approval(approval_id: str, review: ReviewRequest):
    try:
        approvals.approve(approval_id, review.reviewer)
        return resume_approval(approval_id)
    except (KeyError, ValueError, PermissionError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/approvals/{approval_id}/reject")
def reject_approval(approval_id: str, review: ReviewRequest):
    try:
        approval = approvals.reject(approval_id, review.reviewer, review.comment)
        return {"success": True, "message": "Rejected. The dangerous action was not executed.", "approval": approval}
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
