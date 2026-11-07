"""
Unit tests for Milestone M1: Configuration & SQLite Database Layer.
"""

import pytest
from pathlib import Path
from app.config import settings
from app.database import (
    init_db,
    get_stats,
    is_tx_used,
    record_paid_call,
    set_pause_state,
    add_discovery_log,
)


def test_wallet_address_configured():
    """Verify John's Base wallet address is properly configured."""
    assert settings.WALLET_ADDRESS.lower() == "0x1bbae07abebbb61f611391e02e81ee26b0c47b79"
    assert settings.WALLET_ADDRESS.startswith("0x")
    assert len(settings.WALLET_ADDRESS) == 42


def test_database_lifecycle_and_replay_protection(tmp_path: Path):
    """Verify stats initialization, revenue recording, replay protection, and pause toggle."""
    db_file = str(tmp_path / "test_m1.db")
    init_db(db_file)

    stats = get_stats(db_file)
    assert stats["status"] == "ONLINE"
    assert stats["paused"] is False
    assert stats["calls_micro"] == 0
    assert stats["calls_premium"] == 0
    assert stats["revenue_usdc"] == 0.0
    assert len(stats["discoveries"]) >= 1

    # Record a micro call ($0.01)
    tx1 = "0xabc111222333444555666777888999000aaabbbcccdddeeefff1112223334445"
    assert is_tx_used(tx1, db_file) is False
    updated = record_paid_call(
        tx_hash=tx1,
        endpoint="/api/v1/crypto-pulse",
        amount_usdc=0.01,
        tier="micro",
        db_path=db_file,
    )
    assert is_tx_used(tx1, db_file) is True
    assert updated["calls_micro"] == 1
    assert updated["revenue_usdc"] == 0.01

    # Attempt replay attack with same tx_hash
    with pytest.raises(ValueError, match="Transaction hash already used"):
        record_paid_call(
            tx_hash=tx1,
            endpoint="/api/v1/crypto-pulse",
            amount_usdc=0.01,
            tier="micro",
            db_path=db_file,
        )

    # Record a premium call ($1.00)
    tx2 = "0xdef999888777666555444333222111000fffaaabbbcccdddeee1112223334445"
    updated = record_paid_call(
        tx_hash=tx2,
        endpoint="/api/v1/deep-market-report",
        amount_usdc=1.00,
        tier="premium",
        db_path=db_file,
    )
    assert updated["calls_premium"] == 1
    assert updated["revenue_usdc"] == 1.01

    # Test Emergency Stop (Pause)
    paused_state = set_pause_state(True, db_file)
    assert paused_state["paused"] is True
    assert paused_state["status"] == "PAUSED"

    resumed_state = set_pause_state(False, db_file)
    assert resumed_state["paused"] is False
    assert resumed_state["status"] == "ONLINE"

    # Test adding discovery log
    new_log = add_discovery_log(
        topic="Solana Token Liquidity API",
        suggested_endpoint="/api/v1/solana-liquidity",
        suggested_price_usdc=0.02,
        rationale="Hög sökvolym bland trading-agenter.",
        db_path=db_file,
    )
    assert new_log["suggested_endpoint"] == "/api/v1/solana-liquidity"

