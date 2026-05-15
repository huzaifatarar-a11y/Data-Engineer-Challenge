import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

STACK_URL = os.environ.get("STACK_URL", "http://localhost:8000")


@pytest.fixture
def stack_url():
    return STACK_URL
