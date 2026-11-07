"""
Automatic Cloud Persistence Service (Secret GitHub Gist Sync).
- On server startup (if local SQLite is fresh/empty after a Render container redeploy),
  automatically restores the latest snapshot from John's secret GitHub Gist.
- Periodically (and via GitHub Actions Keep-Alive) exports and backs up the live SQLite state.
"""

import json
import logging
from typing import Optional
import httpx

from app.config import settings
from app.database import export_db_snapshot, get_stats, import_db_snapshot

logger = logging.getLogger(__name__)


async def restore_from_cloud_gist(db_path: Optional[str] = None) -> bool:
    """Restore SQLite database from the secret GitHub Gist if available."""
    gist_id = settings.BACKUP_GIST_ID.strip()
    if not gist_id:
        return False

    headers = {"Accept": "application/vnd.github+json"}
    if settings.GITHUB_BACKUP_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_BACKUP_TOKEN}"

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"https://api.github.com/gists/{gist_id}", headers=headers
            )
            if resp.status_code != 200:
                return False
            files = resp.json().get("files", {})
            file_obj = files.get("aim_network_backup.json")
            if not file_obj or not file_obj.get("content"):
                return False
            snapshot = json.loads(file_obj["content"])
            if snapshot and "system_state" in snapshot:
                import_db_snapshot(snapshot, db_path)
                logger.info("Restored SQLite state from Cloud Backup Gist %s", gist_id)
                return True
    except Exception as exc:
        logger.warning("Cloud Gist restore skipped: %s", exc)
    return False


async def push_to_cloud_gist(db_path: Optional[str] = None) -> bool:
    """Push current SQLite snapshot to the secret GitHub Gist (when GITHUB_BACKUP_TOKEN is set)."""
    gist_id = settings.BACKUP_GIST_ID.strip()
    token = settings.GITHUB_BACKUP_TOKEN.strip()
    if not gist_id or not token:
        return False

    snapshot = export_db_snapshot(db_path)
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
    }
    payload = {
        "description": "AIM Network Persistent SQLite Cloud Backup (Auto-Synced)",
        "files": {
            "aim_network_backup.json": {
                "content": json.dumps(snapshot, ensure_ascii=False)
            }
        },
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

