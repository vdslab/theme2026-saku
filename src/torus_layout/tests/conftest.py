"""小規模の実求解をネットワーク不要の同一Gurobi環境で比較する。"""

import gurobipy as gp
import pytest


@pytest.fixture
def local_solver(monkeypatch):
    environments = []

    def create(verbose=False):
        env = gp.Env(params={"OutputFlag": int(verbose)})
        environments.append(env)
        return env

    yield create
    for env in environments:
        env.dispose()
