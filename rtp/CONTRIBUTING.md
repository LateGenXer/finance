# Branches

https://lategenxer-rtp.streamlit.app/ serves the tool from the `stable`
branch.

https://lategenxer-rtp-devel.streamlit.app/ serves the tool from the `main`
branch.  It often gets broken because Streamlit doesn't always handle code
updates gracefully.

# Get started

Follow the [Streamlit installation
guide](https://docs.streamlit.io/library/get-started/installation), using
`pipenv` as environment management tool.

Serve the calculator locally by running

```shell
pipenv run streamlit run rtp/app.py
```

This should start serving the tool locally.

# State override

To avoid re-entering the desired parameters all the time, one can add a
`rtp/devel.py` file containing the desired parameters as a Python dictionary
named `state`, for example:

```python

state = {
    "dob_1": 1980,
    "sipp_1": 500000,
    "sipp_contrib_1": 0,
    "isa": 0,
    "gia": 0,
    "misc_contrib": 0,
    "retirement_year": 2045,
}

```

See the `default_state` dictionary in `rtp/app.py` for the definitive reference of what state
parameters are there.
