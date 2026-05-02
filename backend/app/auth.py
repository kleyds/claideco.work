import os

from fastapi import Header, HTTPException


def require_api_key(x_api_key: str = Header(..., description="Your API key")) -> str:
    expected = os.getenv("API_KEY")
    if not expected:
        raise HTTPException(500, "Server misconfigured: API_KEY env var not set")
    if x_api_key != expected:
        raise HTTPException(401, "Invalid API key")
    return x_api_key
