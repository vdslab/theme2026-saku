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

- コミットメッセージの件名は `prefix: 日本語で変更内容` の形式にする。種類に応じて `dev`（機能開発）、`fix`（不具合修正）、`refactor`（内部構造の整理）、`docs`（文書変更）などの英小文字の接頭辞を選ぶ。例 `fix: 放射型描画の螺旋配線と評価指標を修正`。
