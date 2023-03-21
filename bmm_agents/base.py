import ast
import uuid
from abc import ABC
from typing import List, Literal, Optional, Sequence, Tuple

import nslsii.kafka_utils
import numpy as np
import tiled
from bluesky_adaptive.agents.base import Agent, AgentConsumer
from bluesky_kafka import Publisher
from bluesky_queueserver_api.zmq import REManagerAPI
from numpy.typing import ArrayLike

from .utils import Pandrosus


class BMMBaseAgent(Agent, ABC):
    sample_position_motors = ("xafs_x", "xafs_y")

    def __init__(
        self,
        *args,
        filename: str,
        exp_mode: Literal["fluorescence", "transmission"],
        exp_data_type: Literal["chi", "mu"],
        elements: Sequence[str],
        edges: Sequence[str],
        element_origins: Sequence[Tuple[float, float]],
        element_det_positions: Sequence[float],
        roi: Optional[Tuple] = None,
        sample: str = "Unknown",
        preparation: str = "Unknown",
        exp_bounds: str = "-200 -30 -10 25 12k",
        exp_steps: str = "10 2 0.3 0.05k",
        exp_times: str = "0.5 0.5 0.5 0.5",
        **kwargs,
    ):
        self._filename = filename
        self._edges = edges
        self._exp_mode = exp_mode
        self._abscissa = exp_data_type
        self._ordinate = "k" if exp_data_type == "chi" else "energy"
        self._elements = elements
        self._element_origins = np.array(element_origins)
        self._element_det_positions = np.array(element_det_positions)
        self._roi = roi

        self._sample = sample
        self._preparation = preparation
        self._exp_bounds = exp_bounds
        self._exp_steps = exp_steps
        self._exp_times = exp_times

        _default_kwargs = self.get_beamline_objects()
        _default_kwargs.update(kwargs)
        super().__init__(*args, **_default_kwargs)

    @property
    def filename(self):
        return self._filename

    @filename.setter
    def filename(self, value: str):
        self._filename = value

    @property
    def edges(self):
        return self._edges

    @edges.setter
    def edges(self, value: Sequence[str]):
        self._edges = value

    @property
    def exp_mode(self):
        return self._exp_mode

    @exp_mode.setter
    def exp_mode(self, value: Literal["fluorescence", "transmission"]):
        self._exp_mode = value
        self.close_and_restart(clear_tell_cache=True)

    @property
    def exp_data_type(self):
        return self._abscissa

    @exp_data_type.setter
    def exp_data_type(self, value: Literal["chi", "mu"]):
        self._abscissa = value
        self._ordinate = "k" if value == "chi" else "energy"
        self.close_and_restart(clear_tell_cache=True)

    @property
    def elements(self):
        return self._elements

    @elements.setter
    def elements(self, value: Sequence[str]):
        self._elements = value

    @property
    def element_origins(self):
        return self._element_origins

    @element_origins.setter
    def element_origins(self, value: Sequence[Tuple[float, float]]):
        self._elements_origins = np.array(value)

    @property
    def element_det_positions(self):
        return self._element_det_positions

    @element_det_positions.setter
    def element_det_positions(self, value: Sequence[float]):
        self._element_det_positions = np.array(value)

    @property
    def roi(self):
        return self._roi_key

    @roi.setter
    def roi(self, value: Tuple[float, float]):
        self._roi = value
        self.close_and_restart(clear_tell_cache=True)

    @property
    def sample(self):
        return self._sample

    @sample.setter
    def sample(self, value: str):
        self._sample = value

    @property
    def preparation(self):
        return self._filename

    @preparation.setter
    def preparation(self, value: str):
        self._preparation = value

    @property
    def exp_bounds(self):
        return self._exp_bounds

    @exp_bounds.setter
    def exp_bounds(self, value: str):
        self._exp_bounds = value

    @property
    def exp_steps(self):
        return self._exp_steps

    @exp_steps.setter
    def exp_steps(self, value: str):
        self._exp_steps = value

    @property
    def exp_times(self):
        return self._exp_times

    @exp_times.setter
    def exp_times(self, value: str):
        self._exp_times = value

    def server_registrations(self) -> None:
        # This ensures relevant properties are in the rest API
        self._register_property("filename")
        self._register_property("elements")
        self._register_property("element_origins")
        self._register_property("element_det_positions")
        self._register_property("exp_data_type")
        self._register_property("exp_mode")
        self._register_property("roi")
        self._register_property("sample")
        self._register_property("preparation")
        self._register_property("exp_bounds")
        self._register_property("exp_steps")
        self._register_property("exp_times")
        return super().server_registrations()

    def unpack_run(self, run):
        """Gets Chi(k) and absolute motor position"""
        run_preprocessor = Pandrosus()
        run_preprocessor.fetch(run, mode=self.exp_mode)
        y = getattr(run_preprocessor.group, self.exp_data_type)
        if self.roi is not None:
            ordinate = getattr(run_preprocessor.group, self._ordinate)
            idx_min = np.where(ordinate < self.roi[0])[0][-1] if len(np.where(ordinate < self.roi[0])[0]) else None
            idx_max = np.where(ordinate > self.roi[1])[0][-1] if len(np.where(ordinate > self.roi[1])[0]) else None
            y = y[idx_min:idx_max]
        md = ast.literal_eval(run.start["XDI"]["_comment"][0])
        return md[f"{self.elements[0]}_position"], y

    def measurement_plan(self, relative_point: ArrayLike) -> Tuple[str, List, dict]:
        args = [
            self.sample_position_motors[0],
            *(self.element_origins[:, 0] + relative_point),
            self.sample_position_motors[1],
            *self.element_origins[:, 1],
            *self.element_det_positions,
        ]

        kwargs = dict(
            elements=self.elements,
            edges=self.edges,
            filename=self.filename,
            nscans=1,
            start="next",
            mode=self.exp_mode,
            sample=self.sample,
            preparation=self.preparation,
            bounds=self.exp_bounds,
            steps=self.exp_steps,
            times=self.exp_times,
            snapshots=False,
            md={"relative_position": relative_point},
        )

        return "agent_move_and_measure", args, kwargs

    def trigger_condition(self, uid) -> bool:
        return (
            "XDI" in self.exp_catalog[uid].start
            and self.exp_catalog[uid].start["plan_name"].startswith("scan_nd")
            and self.exp_catalog[uid].start["XDI"]["Element"]["symbol"] == self.elements[0]
        )

    @staticmethod
    def get_beamline_objects() -> dict:
        beamline_tla = "bmm"
        kafka_config = nslsii.kafka_utils._read_bluesky_kafka_config_file(
            config_file_path="/etc/bluesky/kafka.yml"
        )
        qs = REManagerAPI(http_server_uri=f"https://qserver.nsls2.bnl.gov/{beamline_tla}")
        qs.set_authorization_key(api_key=None)

        kafka_consumer = AgentConsumer(
            topics=[
                f"{beamline_tla}.bluesky.runengine.documents",
            ],
            consumer_config=kafka_config["runengine_producer_config"],
            bootstrap_servers=",".join(kafka_config["bootstrap_servers"]),
            group_id=f"echo-{beamline_tla}-{str(uuid.uuid4())[:8]}",
        )

        kafka_producer = Publisher(
            topic=f"{beamline_tla}.mmm.bluesky.adjudicators",
            bootstrap_servers=",".join(kafka_config["bootstrap_servers"]),
            key="{beamline_tla}.key",
            producer_config=kafka_config["runengine_producer_config"],
        )

        return dict(
            kafka_consumer=kafka_consumer,
            kafka_producer=kafka_producer,
            tiled_data_node=tiled.client.from_uri(
                f"https://tiled.nsls2.bnl.gov/api/v1/node/metadata/{beamline_tla}/raw"
            ),
            tiled_agent_node=tiled.client.from_uri(
                f"https://tiled.nsls2.bnl.gov/api/v1/node/metadata/{beamline_tla}/bluesky_sandbox"
            ),
            qserver=qs,
        )
