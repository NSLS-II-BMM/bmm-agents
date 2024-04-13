import logging
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
from bluesky_adaptive.agents.base import MonarchSubjectAgent
from bluesky_adaptive.server import register_variable
from bluesky_queueserver_api import BPlan
from numpy.typing import ArrayLike

from .sklearn import ActiveKmeansAgent

logger = logging.getLogger(__name__)


class KMeansMonarchSubject(MonarchSubjectAgent, ActiveKmeansAgent):
    def __init__(
        self,
        *args,
        pdf_origin: Tuple[float, float],
        pdf_control: bool = False,
        **kwargs,
    ):
        self.pdf_origin = np.array(pdf_origin)
        self._pdf_control = pdf_control
        self.name_prefix = f"{kwargs.get('analyzed_element','')}-"
        super().__init__(*args, **kwargs)

    @property
    def name(self):
        return f"{self.name_prefix}KMeansPDFMonarchBMMSubject"

    @property
    def pdf_control(self):
        return self._pdf_control

    @pdf_control.setter
    def pdf_control(self, value):
        if value in {True, "true", "True", "TRUE", 1}:
            self._pdf_control = True
        else:
            self._pdf_control = False

    def server_registrations(self) -> None:
        register_variable("pdf_origin", self, "pdf_origin")
        self._register_property("PDF Control", "pdf_control")
        return super().server_registrations()

    def subject_measurement_plan(self, relative_point: ArrayLike) -> Tuple[str, List, Dict]:
        point = relative_point + self.pdf_origin
        return "agent_move_and_measure_hanukkah23", [], {"x": point[0], "y": point[1], "exposure": 30}

    def subject_ask(self, batch_size: int) -> Tuple[Sequence[Dict[str, ArrayLike]], Sequence[ArrayLike]]:
        suggestions, centers = self._sample_uncertainty_proxy(batch_size)
        if not isinstance(suggestions, Iterable):
            suggestions = [suggestions]
        _default_doc = dict(
            cluster_centers=centers,
            cache_len=(
                len(self.independent_cache)
                if isinstance(self.independent_cache, list)
                else self.independent_cache.shape[0]
            ),
            latest_data=self.tell_cache[-1],
            requested_batch_size=batch_size,
        )
        docs = [dict(suggestion=suggestion, **_default_doc) for suggestion in suggestions]
        return docs, suggestions

    def subject_ask_condition(self):
        return self.pdf_control

    # ---- TODO: Remove the following block on upstream integration into Bluesky Adaptive ---- #
    def _add_to_queue(
        self,
        next_points,
        uid,
        *,
        re_manager=None,
        position=None,
        plan_factory=None,
    ):
        """
        Adds a single set of points to the queue as bluesky plans

        Parameters
        ----------
        next_points : Iterable
            New points to measure
        uid : str
        re_manager : Optional[bluesky_queueserver_api.api_threads.API_Threads_Mixin]
            Defaults to self.re_manager
        position : Optional[Union[int, Literal['front', 'back']]]
            Defaults to self.queue_add_position
        plan_factory : Optional[Callable]
            Function to generate plans from points. Defaults to self.measurement_plan.
            Callable should return a tuple of (plan_name, args, kwargs)

        Returns
        -------

        """
        for point in next_points:
            plan_name, args, kwargs = self.measurement_plan(point)
            kwargs.setdefault("md", {})
            kwargs["md"].update(self.default_plan_md)
            kwargs["md"]["agent_ask_uid"] = uid
            plan = BPlan(
                plan_name,
                *args,
                **kwargs,
            )
            if re_manager is None:
                re_manager = self.re_manager
            r = re_manager.item_add(plan, pos=self.queue_add_position if position is None else position)
            logger.debug(f"Sent http-server request for point {point}\n." f"Received reponse: {r}")
        return

    def add_suggestions_to_subject_queue(self, batch_size: int):
        """Calls ask, adds suggestions to queue, and writes out event"""
        next_points, uid = self._ask_and_write_events(batch_size, self.subject_ask, "subject_ask")
        logger.info("Issued ask to subject and adding to the queue. {uid}")
        self._add_to_queue(
            next_points,
            uid,
            re_manager=self.subject_re_manager,
            position="front",
            plan_factory=self.subject_measurement_plan,
        )

    # ---- TODO: Remove the following block on upstream integration into Bluesky Adaptive ---- #
