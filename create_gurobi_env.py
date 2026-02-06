"""
gurobipyの環境を作成する関数
"""

import os
from dotenv import load_dotenv
import gurobipy as gp


def create_gurobi_env():
    load_dotenv()

    return gp.Env(
        params={
            "WLSACCESSID": os.getenv("GRB_WLSACCESSID"),
            "WLSSECRET": os.getenv("GRB_WLSSECRET"),
            "LICENSEID": int(os.getenv("GRB_LICENSEID")),
        }
    )
