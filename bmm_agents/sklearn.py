import logging
from typing import Iterable

import numpy as np
from bluesky_adaptive.agents.sklearn import ClusterAgentBase
from bluesky_adaptive.server import register_variable
from numpy.polynomial.polynomial import polyfit, polyval
from numpy.typing import ArrayLike
from scipy.stats import rv_discrete
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression

from .base import BMMBaseAgent
from .utils import discretize, make_hashable, make_wafer_grid_list

logger = logging.getLogger(__name__)


class PassiveKmeansAgent(BMMBaseAgent, ClusterAgentBase):
    def __init__(self, k_clusters, analyzed_element, *args, **kwargs):
        estimator = KMeans(k_clusters)
        _default_kwargs = self.get_beamline_objects()
        _default_kwargs.update(kwargs)

        super().__init__(*args, estimator=estimator, **kwargs)
        self._element_idx = self.elements.index(analyzed_element)

    @property
    def name(self):
        return "BMMPassiveKMeans"

    def clear_caches(self):
        self.independent_cache = []
        self.dependent_cache = []

    def close_and_restart(self, *, clear_tell_cache=False, retell_all=False, reason=""):
        if clear_tell_cache:
            self.clear_caches()
        return super().close_and_restart(clear_tell_cache=clear_tell_cache, retell_all=retell_all, reason=reason)

    @property
    def analyzed_element_and_edge(self):
        return (self.elements[self._element_idx], self.edges[self._element_idx])

    @analyzed_element_and_edge.setter
    def analyzed_element_and_edge(self, value):
        if isinstance(value, int):
            self._element_idx = value
            self.close_and_restart(clear_tell_cache=True, reason="Parameter Change")
        elif isinstance(value, str):
            logger.info("Changing analyzed element and assuming edge")
            self._element_idx = self.elements.index(value)
            self.close_and_restart(clear_tell_cache=True, reason="Parameter Change")
        else:
            logger.warning("Invalid element or index passed to setter. No change made in analyzed element.")

    def server_registrations(self) -> None:
        self._register_method("clear_caches")
        self._register_property("analyzed_element_and_edge")
        return super().server_registrations()

    def trigger_condition(self, uid) -> bool:
        return (
            "XDI" in self.exp_catalog[uid].start
            and self.exp_catalog[uid].start["plan_name"].startswith("scan_nd")
            and self.exp_catalog[uid].start["XDI"]["Element"]["symbol"] == self.analyzed_element_and_edge[0]
        )

    def report(self, **kwargs):
        arr = np.array(self.observable_cache)
        self.model.fit(arr)
        return dict(
            cluster_centers=self.model.cluster_centers_,
            cache_len=len(self.independent_cache),
            latest_data=self.tell_cache[-1],
        )


class ActiveKmeansAgent(PassiveKmeansAgent):
    def __init__(self, *args, bounds: ArrayLike, min_step_size: float = 0.01, **kwargs):
        super().__init__(*args, **kwargs)
        self._bounds = bounds
        self._min_step_size = min_step_size
        self.knowledge_cache = set()  # Discretized knowledge cache of previously asked/told points

    @property
    def name(self):
        return "BMMActiveKMeans"

    @property
    def bounds(self):
        return self._bounds

    @bounds.setter
    def bounds(self, value: ArrayLike):
        self._bounds = value

    @property
    def min_step_size(self):
        return self._min_step_size

    @min_step_size.setter
    def min_step_size(self, value: ArrayLike):
        self._min_step_size = value

    def server_registrations(self) -> None:
        self._register_property("bounds")
        self._register_property("min_step_size")
        return super().server_registrations()

    def tell(self, x, y):
        """A tell that adds to the local discrete knowledge cache, as well as the standard caches.
        Uses relative coords for x"""
        doc = super().tell(x - self.element_origins[0, self._element_idx], y)
        self.knowledge_cache.add(make_hashable(discretize(doc["independent_variable"], self.min_step_size)))
        doc["absolute_position_offset"] = self.element_origins[0, self._element_idx]
        return doc

    def _sample_uncertainty_proxy(self, batch_size=1):
        """Some Dan Olds magic to cast the distance from a cluster as an uncertainty. Then sample there

        Parameters
        ----------
        batch_size : int, optional

        Returns
        -------
        samples : ArrayLike
        centers : ArrayLike
            Kmeans centers for logging
        """
        # Borrowing from Dan's jupyter fun
        # from measurements, perform k-means
        try:
            sorted_independents, sorted_observables = zip(
                *sorted(zip(self.independent_cache, self.observable_cache))
            )
        except ValueError:
            # Multidimensional case
            sorted_independents, sorted_observables = zip(
                *sorted(zip(self.independent_cache, self.observable_cache), key=lambda x: (x[0][0], x[0][1]))
            )

        sorted_independents = np.array(sorted_independents)
        sorted_observables = np.array(sorted_observables)
        self.model.fit(sorted_observables)
        # retreive centers
        centers = self.model.cluster_centers_
        # calculate distances of all measurements from the centers
        distances = self.model.transform(sorted_observables)
        # determine golf-score of each point (minimum value)
        min_landscape = distances.min(axis=1)
        if self.bounds.size == 2:
            # Assume a 1d scan
            # generate 'uncertainty weights' - as a polynomial fit of the golf-score for each point
            _x = np.arange(*self.bounds, self.min_step_size)
            uwx = polyval(_x, polyfit(sorted_independents, min_landscape, deg=5))
            # Chose from the polynomial fit
            return pick_from_distribution(_x, uwx, num_picks=batch_size), centers
        else:
            # assume a 2d scan, use a linear model to predict the uncertainty
            grid = make_wafer_grid_list(*self.bounds.ravel(), step=self.min_step_size)
            uncertainty_preds = LinearRegression().fit(sorted_independents, min_landscape).predict(grid)
            top_indicies = np.argsort(uncertainty_preds)[-batch_size:]
            return grid[top_indicies], centers

    def ask(self, batch_size=1):
        suggestions, centers = self._sample_uncertainty_proxy(batch_size)
        kept_suggestions = []
        if not isinstance(suggestions, Iterable):
            suggestions = [suggestions]
        # Keep non redundant suggestions and add to knowledge cache
        for suggestion in suggestions:
            hashable_suggestion = make_hashable(discretize(suggestion, self.min_step_size))
            if hashable_suggestion in self.knowledge_cache:
                logger.info(
                    f"Suggestion {suggestion} is ignored as already in the knowledge cache: {hashable_suggestion}"
                )
                continue
            else:
                self.knowledge_cache.add(hashable_suggestion)
                kept_suggestions.append(suggestion)

        base_doc = dict(
            cluster_centers=centers,
            cache_len=(
                len(self.independent_cache)
                if isinstance(self.independent_cache, list)
                else self.independent_cache.shape[0]
            ),
            latest_data=self.tell_cache[-1],
            requested_batch_size=batch_size,
            redundant_points_discarded=batch_size - len(kept_suggestions),
            absoute_position_offset=self.element_origins[0, self._element_idx],
        )
        docs = [dict(suggestion=suggestion, **base_doc) for suggestion in kept_suggestions]

        return docs, kept_suggestions


def current_dist_gen(x, px):
    """from distribution defined by p(x), produce a discrete generator.
    This helper function will normalize px as required, and return the generator ready for use.

    use:

    my_gen = current_dist(gen(x,px))

    my_gen.rvs() = xi # random variate of given type

    where xi is a random discrete value, taken from the set x, with probability px.

    my_gen.rvs(size=10) = np.array([xi1, xi2, ..., xi10]) # a size=10 array from distribution.

    If you want to return the probability mass function:

    my_gen.pmf

    See more in scipy.stats.rv_discrete
    """
    px[px < 0] = 0  # ensure non-negativitiy
    return rv_discrete(name="my_gen", values=(x, px / sum(px)))


def pick_from_distribution(x, px, num_picks=1):
    my_gen = current_dist_gen(x, px)
    if num_picks != 1:
        return my_gen.rvs(size=num_picks)
    else:
        return my_gen.rvs()


class MultiElementActiveKmeansAgent(ActiveKmeansAgent):
    """Meant for use with all elements."""

    tell_count = 0

    @property
    def ask_on_tell(self) -> bool:
        if (self.tell_count >= len(self.elements)) and self._ask_on_tell:
            self.tell_count = 0
            return True
        else:
            return False

    @ask_on_tell.setter
    def ask_on_tell(self, flag: bool):
        self._ask_on_tell = flag

    def server_registrations(self) -> None:
        register_variable("internal ask_on_tell", self, "ask_on_tell")
        return super().server_registrations()

    def tell(self, x, y):
        self.tell_count += 1
        return super().tell(x, y)
