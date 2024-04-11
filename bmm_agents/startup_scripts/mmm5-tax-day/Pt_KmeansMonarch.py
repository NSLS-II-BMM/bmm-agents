import logging
import os

import numpy as np
import tiled.client.node  # noqa: F401
from bluesky_adaptive.server import register_variable, shutdown_decorator, startup_decorator
from pdf_agents.agents import PDFBaseAgent

from bmm_agents.monarch_pdf_subject import KMeansMonarchSubject

logger = logging.getLogger(__name__)


beamline_objects = KMeansMonarchSubject.get_beamline_objects()
beamline_objects["qserver"].set_authorization_key(api_key=os.getenv("HTTPSERVER_API_KEY", "zzzzz"))

pdf_objects = PDFBaseAgent.get_beamline_objects()
pdf_objects["qserver"].set_authorization_key(api_key=os.getenv("HTTPSERVER_API_KEY", "yyyyy"))

agent = KMeansMonarchSubject(
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
    # PDF Args
    subject_qserver=pdf_objects["qserver"],
    subject_kafka_producer=pdf_objects["kafka_producer"],
    subject_endstation_key="pdf",
    pdf_origin=(17.574, 4.075),
    # Active Kmeans Args
    bounds=np.array([(-32, 32), (-32, 32)]),
    # BS Adaptive Args
    ask_on_tell=False,
    report_on_tell=True,
    k_clusters=6,
    analyzed_element="Pt",
    queue_add_position="back",
    **beamline_objects
)


@startup_decorator
def startup():
    agent.start()
    path = "/nsls2/data/bmm/shared/config/source/bmm-agents/bmm_agents/startup_scripts/historical_Pt_uids.txt"
    with open(path, "r") as f:
        uids = []
        for line in f:
            uids.append(line.strip().strip(",").strip("'"))

    agent.tell_agent_by_uid(uids)


@shutdown_decorator
def shutdown_agent():
    return agent.stop()


register_variable("Told UIDs", agent, "tell_cache")
register_variable("Agent Name", agent, "instance_name")
