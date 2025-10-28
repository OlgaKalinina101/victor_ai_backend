from pydantic import BaseModel


class TokenRequest(BaseModel):
    user_id: str
    token: str