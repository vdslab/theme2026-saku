"""
gurobipyの環境を作成する関数
"""

import os
from dotenv import load_dotenv
import gurobipy as gp


def create_gurobi_env(verbose=False):
    """Gurobi環境を作成する。

    Args:
        verbose: Trueの場合のみGurobiのコンソールログを表示する。
    """
    load_dotenv()

    return gp.Env(
        params={
            "OutputFlag": 1 if verbose else 0,
            "WLSACCESSID": os.getenv("GRB_WLSACCESSID"),
            "WLSSECRET": os.getenv("GRB_WLSSECRET"),
            "LICENSEID": int(os.getenv("GRB_LICENSEID")),
        }
    )
