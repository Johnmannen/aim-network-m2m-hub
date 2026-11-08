"""
Automatic Cloud Persistence Service (Secret GitHub Gist Sync).
Ensures database state can be restored if container restarts.
All IP addresses and payer addresses are sanitized/redacted before export.
"""

import json
import logging
from typing import Optional
import httpx
from app.config import settings
from app.database import export_db_snapshot, import_db_snapshot

logger = logging.getLogger(__name__)


async def restore_from_cloud_gist(db_path: Optional[str] = None) -> bool:
    """Restore SQLite database from the secret GitHub Gist if available."""
    gist_id = getattr(settings, "BACKUP_GIST_ID", "").strip()
    if not gist_id:
        return False
    token = getattr(settings, "GITHUB_BACKUP_TOKEN", "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "aim-network-cloud-backup",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"https://api.github.com/gists/{gist_id}", headers=headers
            )
            if resp.status_code == 200:
                files = resp.json().get("files", {})
                for fname, file_data in files.items():
                    if fname.endswith(".json") and "content" in file_data:
                        snap = json.loads(file_data["content"])
                        import_db_snapshot(snap, db_path=db_path)
                        logger.info("Restored SQLite state from Cloud Backup Gist %s", gist_id)
                        return True
    except Exception as exc:
        logger.warning("Cloud Gist restore skipped: %s", exc)
    return False


async def push_to_cloud_gist(db_path: Optional[str] = None) -> bool:
    """Push sanitized SQLite snapshot to the secret GitHub Gist (when configured)."""
    gist_id = getattr(settings, "BACKUP_GIST_ID", "").strip()
    token = getattr(settings, "GITHUB_BACKUP_TOKEN", "").strip()
    if not gist_id or not token:
        return False

    snapshot = export_db_snapshot(db_path=db_path)
    # Double ensure all IP addresses are masked
    if "traffic_logs" in snapshot:
        for entry in snapshot["traffic_logs"]:
            if "client_ip" in entry:
                entry["client_ip"] = "redacted"

    payload = {
        "description": "AIM Network SQLite Cloud Backup Snapshot (Sanitized)",
        "files": {
            "aim_network_backup.json": {
                "content": json.dumps(snapshot, indent=2)
            }
        },
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "aim-network-cloud-backup",
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.patch(
                f"https://api.github.com/gists/{gist_id}",
                headers=headers,
                json=payload,
            )
            return resp.status_code == 200
    except Exception as exc:
        logger.warning("Cloud Gist backup push failed: %s", exc)
        return False

