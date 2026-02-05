def create_gurobi_env():
    import os
    from dotenv import load_dotenv
    import gurobipy as gp

    load_dotenv()

    return gp.Env(
        params={
            "WLSACCESSID": os.getenv("GRB_WLSACCESSID"),
            "WLSSECRET": os.getenv("GRB_WLSSECRET"),
            "LICENSEID": int(os.getenv("GRB_LICENSEID")),
        }
    )
