from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator

from ufo.agents.processors.schemas.actions import ActionCommandInfo


class HostAgentResponse(BaseModel):
    """
    The response data for the HostAgent.
    """

    observation: str
    thought: str
    status: str
    message: Optional[List[str]] = None
    questions: Optional[List[str]] = None
    current_subtask: Optional[str] = None
    plan: Optional[List[str]] = None
    comment: Optional[str] = None
    function: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None


class AppAgentResponse(BaseModel):
    """
    The multi-action response data for the AppAgent.
    """

    observation: str
    thought: str
    plan: Optional[List[str]] = None
    comment: Optional[str] = None
    action: Union[List[ActionCommandInfo], ActionCommandInfo, None] = None
    save_screenshot: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Any] = None

    @field_validator("save_screenshot", mode="before")
    @classmethod
    def normalize_save_screenshot(cls, value: Any) -> Dict[str, Any]:
        """Accept Qwen's compact boolean form and expose one stable shape."""
        if isinstance(value, bool):
            # Models often emit false/true instead of the documented object.
            # Normalize it here so screenshot consumers never call .get() on bool.
            return {"save": value, "reason": ""}
        if value is None:
            return {}
        return value


class EvaluationAgentResponse(BaseModel):
    """
    The response data for the EvaluationAgent.
    """

    complete: str
    sub_scores: Optional[List[Dict[str, str]]] = None
    reason: Optional[str] = None
