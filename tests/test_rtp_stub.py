import pytest

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    pytest.skip("No Streamlit; skipping.", allow_module_level=True)


@pytest.fixture(scope="function")
def at():
    at = AppTest.from_file("rtp/app.py", default_timeout=10)
    at.run()
    return at


def test_run(at):
    # Ensure no state corruption
    at.run()
    assert not at.exception
