"""
Configuration module for AIM Network (Autonomous M2M API Hub).
Loads environment variables from .env with strict security defaults.
"""

import os
import secrets
from decimal import Decimal
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Ephemeral fallback tokens generated per process if not set in env (distinct for Admin, Scout, and Session)
_GENERATED_FALLBACK_PIN = secrets.token_urlsafe(24)
_GENERATED_FALLBACK_SCOUT = secrets.token_urlsafe(24)
_GENERATED_FALLBACK_SESSION = secrets.token_urlsafe(32)


class Settings:
    """Centralized application settings."""

    PROJECT_NAME: str = "AIM Network - Autonomous M2M API Hub"
    VERSION: str = "1.1.0"
    CANONICAL_BASE_URL: str = os.getenv(
        "CANONICAL_BASE_URL", "https://johngarp.click"
    ).rstrip("/")

    # Base L2 USDC recipient address
    WALLET_ADDRESS: str = os.getenv(
        "WALLET_ADDRESS", "0x1bbae07abebbb61f611391e02e81ee26b0c47b79"
    )

    # Admin security token/PIN, separate Scout/Backup token, and Session signing secret
    ADMIN_PIN: str = os.getenv("ADMIN_PIN", "") or _GENERATED_FALLBACK_PIN
    SCOUT_SECRET_TOKEN: str = (
        os.getenv("SCOUT_SECRET_TOKEN", "") or _GENERATED_FALLBACK_SCOUT
    )
    SESSION_SECRET: str = os.getenv("SESSION_SECRET", "") or _GENERATED_FALLBACK_SESSION
    SESSION_MAX_AGE_SECONDS: int = int(
        os.getenv("SESSION_MAX_AGE_SECONDS", str(4 * 3600))
    )
    TRAFFIC_RETENTION_DAYS: int = int(os.getenv("TRAFFIC_RETENTION_DAYS", "30"))

    # Production default is ALWAYS "strict_onchain".
    # Simulated `test_tx_` tokens are only accepted when TESTING=true AND X402_VERIFY_MODE=hybrid.
    X402_VERIFY_MODE: str = os.getenv("X402_VERIFY_MODE", "strict_onchain")
    TESTING: bool = os.getenv("TESTING", "false").lower() in ("true", "1", "yes")

    # Public Base Mainnet RPC + Fallback RPCs & Native USDC contract on Base (Chain ID 8453)
    BASE_CHAIN_ID: int = 8453
    BASE_RPC_URL: str = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
    BASE_RPC_FALLBACKS: list[str] = [
        "https://mainnet.base.org",
        "https://base.llamarpc.com",
        "https://1rpc.io/base",
    ]
    USDC_CONTRACT_ADDRESS: str = os.getenv(
        "USDC_CONTRACT_ADDRESS", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    )

    # Rate Limiting & PIN Brute-Force Lockout
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    TRUST_PROXY_HEADERS: bool = (
        os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true"
    )
    MAX_PIN_FAILURES: int = 5
    PIN_LOCKOUT_SECONDS: int = 900  # 15 minutes
    MIN_CONFIRMATIONS: int = int(os.getenv("MIN_CONFIRMATIONS", "1"))

    # Standard x402 (EIP-3009 via facilitator). Empty URL = standard flow disabled.
    X402_FACILITATOR_URL: str = os.getenv("X402_FACILITATOR_URL", "").strip()
    X402_FACILITATOR_AUTH: str = os.getenv("X402_FACILITATOR_AUTH", "").strip()

    # Pricing tiers in USDC (Decimal-safe)
    PRICE_MICRO_DEC: Decimal = Decimal("0.01")
    PRICE_DYNAMIC_DEC: Decimal = Decimal("0.05")
    PRICE_DEX_RADAR_DEC: Decimal = Decimal("0.05")
    PRICE_PREMIUM_DEC: Decimal = Decimal("1.00")
    PRICE_VIP_24H_DEC: Decimal = Decimal("2.00")
    PRO_PASS_PRICE_DEC: Decimal = Decimal("10.00")

    PRICE_MICRO_USDC: float = float(PRICE_MICRO_DEC)
    PRICE_DYNAMIC_USDC: float = float(PRICE_DYNAMIC_DEC)
    PRICE_DEX_RADAR_USDC: float = float(PRICE_DEX_RADAR_DEC)
    PRICE_PREMIUM_USDC: float = float(PRICE_PREMIUM_DEC)
    PRICE_VIP_24H_USDC: float = float(PRICE_VIP_24H_DEC)

    VIP_PASS_MAX_CALLS: int = 500
    VIP_PASS_DURATION_HOURS: int = 24

    PRO_PASS_MAX_CALLS: int = 50
    PRO_PASS_DURATION_HOURS: int = 24

    # On-Chain Payment Verification Security (P2: Max Transaction Age < 15 minutes)
    MAX_TX_AGE_SECONDS: int = int(os.getenv("MAX_TX_AGE_SECONDS", "900"))

    # First-Time Buyer Welcome Bonus (Sybil-resistant on-chain onboarding reward)
    WELCOME_BONUS_ENABLED: bool = (
        os.getenv("WELCOME_BONUS_ENABLED", "true").lower() == "true"
    )
    WELCOME_BONUS_CALLS: int = int(os.getenv("WELCOME_BONUS_CALLS", "5"))
    WELCOME_BONUS_DURATION_HOURS: int = int(
        os.getenv("WELCOME_BONUS_DURATION_HOURS", "24")
    )

    # Autonomous Scout Auto-Pilot interval in seconds (default: every 3600s = 1 hour)
    SCOUT_INTERVAL_SECONDS: int = int(os.getenv("SCOUT_INTERVAL_SECONDS", "3600"))
    SCOUT_AUTOPILOT_ENABLED: bool = (
        os.getenv("SCOUT_AUTOPILOT_ENABLED", "true").lower() == "true"
    )

    # SQLite database storage path (local SSD / persistent disk)
    DATABASE_PATH: str = os.getenv(
        "DATABASE_PATH", str(BASE_DIR / "data" / "aim_network.db")
    )
    BACKUP_GIST_ID: str = os.getenv("BACKUP_GIST_ID", "")
    GITHUB_BACKUP_TOKEN: str = os.getenv("GITHUB_BACKUP_TOKEN", "")


settings = Settings()
