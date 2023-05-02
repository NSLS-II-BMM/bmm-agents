import logging
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
from bluesky_adaptive.agents.base import MonarchSubjectAgent
from bluesky_adaptive.server import register_variable
from numpy.typing import ArrayLike

from .sklearn import MultiElementActiveKmeansAgent

logger = logging.getLogger(__name__)


class KMeansMonarchSubject(MonarchSubjectAgent, MultiElementActiveKmeansAgent):
    def __init__(
        self,
        *args,
        pdf_origin: Tuple[float, float],
        **kwargs,
    ):
        self.pdf_origin = np.array(pdf_origin)
        super().__init__(*args, **kwargs)

    @property
    def name(self):
        return "KMeansPDFMonarchBMMSubject"

    def server_registrations(self) -> None:
        register_variable("pdf_origin", self, "pdf_origin")
        return super().server_registrations()

    def subject_measurement_plan(self, relative_point: ArrayLike) -> Tuple[str, List, Dict]:
        return "agent_redisAware_PDFcount", [relative_point + self.pdf_origin[0]], {}

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
        return True
