"""
Global pytest configuration for AIM Network.
Enables TESTING mode during test runs so simulated sandbox proofs (`test_tx_...`) can be tested
while production defaults remain strictly `strict_onchain`.
"""

import os
import pytest

os.environ["TESTING"] = "true"
os.environ["X402_VERIFY_MODE"] = "hybrid"

from app.config import settings
from app.routers.dashboard import _pin_failures

settings.TESTING = True
settings.X402_VERIFY_MODE = "hybrid"


@pytest.fixture(autouse=True)
def reset_pin_lockout_between_tests():
    """Ensure brute-force lockout map is clean before each test."""
    _pin_failures.clear()
    settings.TESTING = True
    settings.X402_VERIFY_MODE = "hybrid"
    yield
    _pin_failures.clear()
