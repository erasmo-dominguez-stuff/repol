# conftest.py for shared fixtures
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

@pytest.fixture
def sample_policy_config():
    return {
        "approvals_required": 2,
        "allowed_branches": ["main"],
        "tests_passed": True,
        "signed_off": True,
        "max_deployments_per_day": 5
    }

@pytest.fixture
def sample_event():
    return {
        "deployment": {
            "ref": "main",
            "environment": "production"
        },
        "environment": "production"
    }
