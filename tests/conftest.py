"""
conftest.py — Global Test Configuration and Safety Fixtures
===========================================================
Guarantees that no test in the test suite can ever touch or query
the real platformdirs user data directory.
"""

import pytest
import wontnote.vault_storage


@pytest.fixture(autouse=True, scope="session")
def guard_real_user_data_dir():
    """
    Session-level autouse fixture.
    Monkeypatches wontnote.vault_storage.user_data_dir to raise RuntimeError
    if called without an explicit test override, ensuring tests cannot touch
    the real user data directory.
    """
    def forbidden_user_data_dir(*args, **kwargs):
        raise RuntimeError(
            "CRITICAL SAFETY VIOLATION: A test attempted to query or access "
            "the real user data directory without providing an isolated path!"
        )

    original_user_data_dir = wontnote.vault_storage.user_data_dir
    wontnote.vault_storage.user_data_dir = forbidden_user_data_dir
    yield
    wontnote.vault_storage.user_data_dir = original_user_data_dir
