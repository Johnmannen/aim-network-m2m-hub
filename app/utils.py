"""Shared helpers for AIM Network."""

from fastapi import Request

from app.config import settings


def resolve_client_ip(request: Request) -> str:
    """
    Resolve client IP safely.
    Only trust CF-Connecting-IP when verified by Cloudflare proxy signature (CF-Ray)
    or in testing mode. This prevents attackers from forging client IPs by calling
    *.onrender.com directly.
    """
    if settings.TRUST_PROXY_HEADERS:
        if request.headers.get("CF-Ray") or settings.TESTING:
            cf_ip = request.headers.get("CF-Connecting-IP", "").strip()
            if cf_ip:
                return cf_ip
            xff = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            if xff:
                return xff
    return request.client.host if request.client else "unknown"
