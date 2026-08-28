from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uuid

from .dependencies import get_orchestrator, get_policy, POLICIES
from src.orchestrator.pipeline import PipelineOrchestrator
from src.policy.schemas import UseCasePolicy

router = APIRouter()

class ChatRequest(BaseModel):
    prompt: str
    policy_id: str = "standard"
    session_id: Optional[str] = None

@router.get("/policies")
def get_available_policies():
    """Returns the list of available policies for the UI dropdown."""
    return {
        "policies": [
            {
                "id": pid,
                "name": policy.name,
                "description": policy.description
            }
            for pid, policy in POLICIES.items()
        ]
    }

@router.post("/chat")
def chat(request: ChatRequest, orchestrator: PipelineOrchestrator = Depends(get_orchestrator)):
    """
    Main endpoint for generating text.
    Passes the prompt and the requested Use-Case Policy into the PipelineOrchestrator.
    """
    if request.policy_id not in POLICIES:
        raise HTTPException(status_code=400, detail=f"Invalid policy_id. Must be one of {list(POLICIES.keys())}")
        
    policy = get_policy(request.policy_id)
    
    session_id = request.session_id if request.session_id else str(uuid.uuid4())
    
    # Process the request end-to-end
    result_dict = orchestrator.process_request(prompt=request.prompt, policy=policy, user_id="demo_user", session_id=session_id)
    
    # Return session_id to client so they can maintain session
    result_dict["session_id"] = session_id
    
    return result_dict
