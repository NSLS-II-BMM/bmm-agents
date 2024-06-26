import numpy as np
import tiled.client.node
from bluesky_adaptive.server import register_variable, shutdown_decorator, startup_decorator

from bmm_agents.sklearn import MultiElementActiveKmeansAgent

agent = MultiElementActiveKmeansAgent(
    filename="PtNi-Multimodal-PtDrivenKmeans",
    exp_mode="fluorescence",
    read_mode="transmission",
    exp_data_type="mu",
    elements=["Pt", "Ni"],
    edges=["L3", "K"],
    element_origins=[[186.307, 89.276], [186.384, 89.305]],
    element_det_positions=[185, 160],
    sample="AlPtNi wafer pretend-binary PtNi",
    preparation="AlPtNi codeposited on a silica wafer",
    exp_bounds="-200 -30 -10 25 13k",
    exp_steps="10 2 0.5 0.05k",
    exp_times="1 1 1 1",
    bounds=np.array([(-32, 32), (-32, 32)]),
    ask_on_tell=False,
    report_on_tell=True,
    k_clusters=6,
    analyzed_element="Pt",
)


@startup_decorator
def startup():
    agent.start()
    path = "/nsls2/data/pdf/shared/config/source/bmm-agents/bmm_agents/startup_scripts/historical_Pt_uids.txt"
    with open(path, "r") as f:
        uids = []
        for line in f:
            uids.append(line.strip().strip(",").strip("'"))

    agent.tell_agent_by_uid(uids)


@shutdown_decorator
def shutdown_agent():
    return agent.stop()


register_variable("tell cache", agent, "tell_cache")
register_variable("agent name", agent, "instance_name")
