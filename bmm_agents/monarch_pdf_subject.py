import logging
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
from bluesky_adaptive.agents.base import MonarchSubjectAgent
from bluesky_adaptive.server import register_variable
from numpy.typing import ArrayLike

from .sklearn import ActiveKmeansAgent

logger = logging.getLogger(__name__)


class KMeansMonarchSubject(MonarchSubjectAgent, ActiveKmeansAgent):
    def __init__(
        self,
        *args,
        pdf_origin: Tuple[float, float],
        **kwargs,
    ):
        self.pdf_origin = np.array(pdf_origin)
        self._pdf_control = False
        super().__init__(*args, **kwargs)

    @property
    def name(self):
        return "{self.analyzed_element}-KMeansPDFMonarchBMMSubject"

    @property
    def pdf_control(self):
        return self._pdf_control

    @pdf_control.setter
    def pdf_control(self, value):
        if value in {True, "true", "True", "TRUE", 1}:
            self.pdf_control = True
        else:
            self.pdf_control = False

    def server_registrations(self) -> None:
        register_variable("pdf_origin", self, "pdf_origin")
        self._register_property("pdf_control")
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
