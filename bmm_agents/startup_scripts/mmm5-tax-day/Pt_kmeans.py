import os

import numpy as np
import tiled.client.node  # noqa: F401
from bluesky_adaptive.server import register_variable, shutdown_decorator, startup_decorator

from bmm_agents.sklearn import ActiveKmeansAgent

beamline_objects = ActiveKmeansAgent.get_beamline_objects()
beamline_objects["qserver"].set_authorization_key(api_key=os.getenv("HTTPSERVER_API_KEY", "zzzzz"))


old_mmm4_origin = [[186.307, 89.276], [186.384, 89.305]]
new_mmm5_origin = [[174.550, 103.806], [175.127, 103.484]]

agent = ActiveKmeansAgent(
    filename="PtNi-Multimodal-PtDrivenKmeans",
    exp_mode="fluorescence",
    read_mode="transmission",
    exp_data_type="mu",
    elements=["Pt", "Ni"],
    edges=["L3", "K"],
    element_origins=new_mmm5_origin,
    element_det_positions=[180, 110],
    sample="AlPtNi wafer pretend-binary PtNi",
    preparation="AlPtNi codeposited on a silica wafer",
    exp_bounds="-200 -30 -10 25 13k",
    exp_steps="10 2 0.3 0.05k",
    exp_times="1 1 1 1",
    variable_motor_names=("xafs_x", "xafs_y"),
    bounds=np.array([(-31, 31), (-31, 31)]),
    ask_on_tell=False,
    report_on_tell=True,
    k_clusters=6,
    analyzed_element="Pt",
    **beamline_objects
)


@startup_decorator
def startup():
    agent.start()
    path = "/nsls2/data/bmm/shared/config/source/bmm-agents/bmm_agents/startup_scripts/historical_mmm4_uids.txt"
    with open(path, "r") as f:
        uids = []
        for line in f:
            uid = line.strip().strip(",").strip("'")
            if agent.trigger_condition(uid):
                uids.append(uid)

    agent.element_origins = old_mmm4_origin
    agent.tell_agent_by_uid(uids)
    agent.element_origins = new_mmm5_origin


@shutdown_decorator
def shutdown_agent():
    return agent.stop()


register_variable("Told UIDs", agent, "tell_cache")
register_variable("Agent Name", agent, "instance_name")
