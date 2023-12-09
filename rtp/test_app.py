import pytest

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    pytest.skip("No Streamlit; skipping.", allow_module_level=True)


# Avoid slider state corruption due to the formating.
def reset_slider(at, key):
    slider = at.select_slider(key=key)
    slider.set_value(f'{slider.value:.0%}')


def run(at):
    at.run()
    reset_slider(at, 'marginal_income_tax_1')
    reset_slider(at, 'marginal_income_tax_2')


@pytest.fixture(scope='module')
def at():
    print("--- at- ----")
    at = AppTest.from_file("app.py", default_timeout=10)
    run(at)
    return at


def test_run(at):
    # Ensure no state corruption
    run(at)
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
    run(at)
    assert not at.exception


def test_lacs(at, submit):
    joint = at.checkbox(key="joint")
    joint.set_value(True)

    # Toggle LACS checkbox
    lacs = at.checkbox(key="lacs")
    lacs.set_value(not lacs.value)
    submit.click()
    run(at)
    assert not at.exception


def test_lump_sum(at, submit):
    joint = at.checkbox(key="joint")
    joint.set_value(True)

    # Set a lump sum
    lump_sum = at.number_input(key="lump_sum")
    assert lump_sum.value == 0
    lump_sum.set_value(1000)
    submit.click()
    run(at)
    assert not at.exception


def test_error(at, submit):
    assert len(at.error) == 0
    joint = at.checkbox(key="joint")
    joint.set_value(False)
    retirement_income_net = at.number_input(key="retirement_income_net")
    retirement_income_net.set_value(1000000)
    submit.click()
    run(at)
    assert not at.exception
    assert len(at.error) == 1

