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


@pytest.fixture(scope="function")
def submit(at):
    assert len(at.button) == 1
    submit = at.button[0]
    return submit


def test_joint(at):
    # Toggle Joint checkbox
    joint = at.checkbox(key="joint")
    joint.set_value(not joint.value)
    at.run()
    assert not at.exception


def test_lump_sum(at, submit):
    joint = at.checkbox(key="joint")
    joint.set_value(True)

    # Set a lump sum
    lump_sum = at.number_input(key="lump_sum")
    assert lump_sum.value == 0
    lump_sum.set_value(1000)
    submit.click()
    at.run()
    assert not at.exception


def test_error(at, submit):
    assert len(at.error) == 0
    joint = at.checkbox(key="joint")
    joint.set_value(False)
    retirement_income_net = at.number_input(key="retirement_income_net")
    retirement_income_net.set_value(1000000)
    submit.click()
    at.run()
    assert not at.exception
    assert len(at.error) == 1

