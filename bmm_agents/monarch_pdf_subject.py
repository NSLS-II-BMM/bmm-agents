import logging
from typing import Dict, Iterable, List, Sequence, Tuple

from bluesky_adaptive.agents.base import MonarchSubjectAgent
from numpy.typing import ArrayLike
from pdf_agent.agents import PDFBaseAgent

from .sklearn import MultiElementActiveKmeansAgent

logger = logging.getLogger(__name__)


class KMeansMonarchSubject(MonarchSubjectAgent, MultiElementActiveKmeansAgent):
    def __init__(
        self,
        *args,
        pdf_origin: Tuple[float, float],
        **kwargs,
    ):
        self._pdf_origin = pdf_origin
        super().__init__(*args, **kwargs)

    @property
    def name(self):
        "KMeansPDFMonarchBMMSubject"

    @property
    def pdf_sample_number(self):
        """XPDAQ Sample Number"""
        return self._pdf_sample_number

    @pdf_sample_number.setter
    def pdf_sample_number(self, value: int):
        self._pdf_sample_number = value

    def subject_measurement_plan(self, relative_point: ArrayLike) -> Tuple[str, List, Dict]:
        return PDFBaseAgent.measurement_plan(relative_point + self._pdf_origin)

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
