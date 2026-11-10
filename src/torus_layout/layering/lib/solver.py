"""既存のGurobi環境設定。環境生成は求解時のみ行う。"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import cast
import gurobipy as gp
from dotenv import load_dotenv

_local_license: ContextVar[bool] = ContextVar("torus_layout_local_license", default=False)


@contextmanager
def use_local_license(enabled: bool = True) -> Iterator[None]:
    """Explicit, scoped local-license selection; never a silent WLS fallback."""
    token = _local_license.set(enabled)
    try:
        yield
    finally:
        _local_license.reset(token)


def create_gurobi_env(verbose: bool = False) -> gp.Env:
    if _local_license.get():
        return gp.Env(params={"OutputFlag": int(verbose)})
    load_dotenv()
    return gp.Env(
        params={
            "OutputFlag": 1 if verbose else 0,
            "WLSACCESSID": cast(str, os.getenv("GRB_WLSACCESSID")),
            "WLSSECRET": cast(str, os.getenv("GRB_WLSSECRET")),
            # Required by the existing .env contract. cast leaves the original
            # int(None) failure unchanged if configuration is missing.
            "LICENSEID": int(cast(str, os.getenv("GRB_LICENSEID"))),
        }
    )
