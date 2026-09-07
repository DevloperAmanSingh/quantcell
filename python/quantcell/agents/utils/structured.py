"""Parse LLM text output into Pydantic models, tolerating fences and prose."""

import json
import re
from typing import Optional, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_json_model(text: str, model_cls: Type[T]) -> Optional[T]:
    """Parse `text` into `model_cls`; returns None when unsalvageable.

    Handles common LLM formatting: markdown code fences and JSON embedded in
    surrounding prose (outermost-braces salvage).
    """
    cleaned = _CODE_FENCE_RE.sub("", (text or "").strip()).strip()
    try:
        return model_cls.model_validate_json(cleaned)
    except Exception:
        pass
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return model_cls.model_validate(json.loads(cleaned[start : end + 1]))
        except Exception:
            pass
    return None


def json_schema_instruction(model_cls: Type[BaseModel]) -> str:
    """A one-line instruction demanding pure JSON matching the model schema."""
    return (
        "Respond with ONLY valid JSON (no markdown, no comments) conforming to "
        f"this JSON schema:\n{json.dumps(model_cls.model_json_schema())}"
    )
