# turbo-trade-star-scenario

## Setting up local env

[Installing pip in virtual env](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/)

create a new virtual env
```bash
python3 -m venv .venv
```

activate the virtual env
```bash
source .venv/bin/activate
```

check if virtual env is activated
```bash
which python
```

cmd to deactivate the virtual env (optional)
```bash
deactivate
```

installing pip
```bash
python3 -m pip install --upgrade pip
```

check the version to verify if pip is installed in virtual env correctly

```bash
pip --version
```

now we can install any dependencies using pip commands

for instslling dependencies for this project (recommended for the first time setup)
```bash
pip install -r requirements.txt
```

To run tests
Install pytest
```bash
pip install -U pytest
```

To run the backtest with default config
```bash
python main.py
```

To expose an api with config inputs for running backtest
```bash
uvicorn api:app --reload
```
The terminal will show the details of the port and address where the api is exposed
something like `http://127.0.0.1:8000`
we can test if everything is working, by accessing this in a browser or postman

Note: Change the db constant for inital setup at `/data/constants.py` to use the sample db commited in the code files
