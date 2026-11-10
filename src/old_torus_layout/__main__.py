"""旧トーラスパイプラインのモジュール実行入口。"""

from runpy import run_module


if __name__ == "__main__":
    run_module("old_torus_layout.main", run_name="__main__")
