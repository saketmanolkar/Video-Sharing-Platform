import pytest
from django.conf import settings

@pytest.fixture(scope='session', autouse=True)
def set_test_settings():
    settings.TESTING = True
    yield
    # Optionally reset after tests complete
    settings.TESTING = False