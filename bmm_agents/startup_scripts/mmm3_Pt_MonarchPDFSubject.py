import logging

from bluesky_adaptive.server import register_variable, shutdown_decorator, startup_decorator
from pdf_agents.agents import PDFBaseAgent

from bmm_agents.monarch_pdf_subject import KMeansMonarchSubject

logger = logging.getLogger(__name__)


pdf_objects = PDFBaseAgent.get_beamline_objects()

agent = KMeansMonarchSubject(
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
    subject_qserver=pdf_objects["qserver"],
    subject_kafka_producer=pdf_objects["kafka_producer"],
    subject_endstation_key="pdf",
    pdf_origin=(17.574, 4.075),
    bounds=(-29, 29),
    ask_on_tell=True,
    report_on_tell=True,
    queue_add_position="back",
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

        # Added for a manual knock down and debug
        uids.append("ecef0421-e464-45e1-be6c-c532d7063708")
        uids.append("256d67c5-6b3c-4738-8046-6838721084fc")
        uids.append("ba02aa32-de24-431e-ba42-830243fc01e6")

    agent.tell_agent_by_uid(uids)
    agent.add_suggestions_to_queue(1)
    agent.add_suggestions_to_subject_queue(6)


@shutdown_decorator
def shutdown_agent():
    return agent.stop()


register_variable("tell cache", agent, "tell_cache")
register_variable("agent name", agent, "instance_name")
register_variable("tell_count", agent, "tell_count")
