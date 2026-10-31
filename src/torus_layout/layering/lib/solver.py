"""既存のGurobi環境設定。環境生成は求解時のみ行う。"""
import os
import gurobipy as gp
from dotenv import load_dotenv

def create_gurobi_env(verbose: bool = False) -> gp.Env:
    load_dotenv()
    return gp.Env(params={
        "OutputFlag": 1 if verbose else 0,
        "WLSACCESSID": os.getenv("GRB_WLSACCESSID"),
        "WLSSECRET": os.getenv("GRB_WLSSECRET"),
        "LICENSEID": int(os.getenv("GRB_LICENSEID")),
    })
