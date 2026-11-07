"""Shared helpers."""

from fastapi import Request

from app.config import settings


def resolve_client_ip(request: Request) -> str:
    """
    Resolve client IP safely. Only trust CF-Connecting-IP / X-Forwarded-For
    when TRUST_PROXY_HEADERS=true (e.g., behind Cloudflare/Render proxy).
    """
    if settings.TRUST_PROXY_HEADERS:
        cf_ip = request.headers.get("CF-Connecting-IP", "").strip()
        if cf_ip:
            return cf_ip
        xff = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if xff:
            return xff
    return request.client.host if request.client else "unknown"

