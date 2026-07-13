# Development environment

- This repository's Python virtual environment is `./theme2026-saku/`.
- For every Python command, use `./theme2026-saku/bin/python`. Do not use bare
  `python`, `python3`, or the system interpreter.
- Install or inspect packages with `./theme2026-saku/bin/python -m pip`.
- When importing modules from `src`, either run scripts as
  `./theme2026-saku/bin/python src/<script>.py` or set `PYTHONPATH=src`.
- Before reporting that `gurobipy` or another Python dependency is missing,
  verify it with the project interpreter, for example:

  ```sh
  ./theme2026-saku/bin/python -c "import gurobipy; print(gurobipy.__version__)"
  ```

- The root `.env` contains the Gurobi configuration used by the application.
  Do not print or copy its secret values.

