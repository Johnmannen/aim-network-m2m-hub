"""
Configuration module for AIM Network (Autonomous M2M API Hub).
Loads environment variables from .env with safe defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Centralized application settings."""

    PROJECT_NAME: str = "AIM Network — Autonomous M2M API Hub"
    VERSION: str = "1.0.0"

    # Base L2 USDC recipient address (John's wallet)
    WALLET_ADDRESS: str = os.getenv(
        "WALLET_ADDRESS", "0x1bbae07abebbb61f611391e02e81ee26b0c47b79"
    )

    # Admin security PIN for Emergency Stop & manual triggers
    ADMIN_PIN: str = os.getenv("ADMIN_PIN", "2026")

    # x402 verification mode: "hybrid" or "strict_onchain"
    X402_VERIFY_MODE: str = os.getenv("X402_VERIFY_MODE", "hybrid")

    # Public Base Mainnet RPC + Fallback RPCs & Native USDC contract on Base
    BASE_RPC_URL: str = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
    BASE_RPC_FALLBACKS: list[str] = [
        "https://mainnet.base.org",
        "https://base.llamarpc.com",
        "https://1rpc.io/base",
    ]
    USDC_CONTRACT_ADDRESS: str = os.getenv(
        "USDC_CONTRACT_ADDRESS", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    )

    # Rate Limiting (requests per 60s window per IP on unpaid endpoints)
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

    # Pricing tiers in USDC
    PRICE_MICRO_USDC: float = 0.01
    PRICE_PREMIUM_USDC: float = 1.00

    # SQLite database path
    DATABASE_PATH: str = os.getenv(
        "DATABASE_PATH", str(BASE_DIR / "data" / "aim_network.db")
    )


settings = Settings()

