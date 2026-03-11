
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from radd.auth.service import decode_token
from radd.config import settings

def key_func(request: Request) -> str:
    """
    Determines the identifier for rate limiting.
    1. Tries to use `workspace_id` from the JWT for authenticated requests.
    2. Falls back to the client's IP address for unauthenticated requests.
    """
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = decode_token(token)
            workspace_id = payload.get("workspace_id")
            if workspace_id:
                return str(workspace_id)
        except ValueError:
            pass

    return get_remote_address(request)

limiter = Limiter(key_func=key_func, storage_uri=settings.redis_url)
