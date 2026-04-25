from pydantic import BaseModel
from typing import Optional

class RequestData(BaseModel):
    text: str
    context: Optional[str] = None