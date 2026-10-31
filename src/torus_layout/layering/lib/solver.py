"""既存のGurobi環境設定。環境生成は求解時のみ行う。"""

import os
from typing import cast
import gurobipy as gp
from dotenv import load_dotenv


def create_gurobi_env(verbose: bool = False) -> gp.Env:
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
