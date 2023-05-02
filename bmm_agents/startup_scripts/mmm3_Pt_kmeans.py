from bluesky_adaptive.server import register_variable, shutdown_decorator, startup_decorator

from bmm_agents.sklearn import MultiElementActiveKmeansAgent

agent = MultiElementActiveKmeansAgent(
    filename="Pt-Zr-Multimodal-PtDrivenKmeans",
    exp_mode="fluorescence",
    read_mode="transmission",
    exp_data_type="mu",
    elements=["Pt", "Zr"],
    edges=["L3", "K"],
    element_origins=[[152.341, 119.534], [152.568, 119.632]],
    element_det_positions=[170, 120],
    sample="PtZr wafer 2",
    preparation="PtZr codeposited on a silica wafer",
    exp_bounds="-200 -30 -10 25 13k",
    exp_steps="10 2 0.5 0.05k",
    exp_times="1 1 1 1",
    bounds=(-29, 29),
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
    agent.ask_on_tell = True
    agent.add_suggestions_to_queue(1)


@shutdown_decorator
def shutdown_agent():
    return agent.stop()


register_variable("tell cache", agent, "tell_cache")
register_variable("agent name", agent, "instance_name")
