from typing import Sequence

import redis
from bluesky import plan_stubs as bps


# ================================== Included for Linter =================================== #
def xafs(*args, filename, **kwargs):
    """Core plan in BMM startup"""
    ...


def change_edge(*args, **kwargs):
    """Change energy in BMM startup"""
    ...


xafs_det = ...
slits3 = ...

# ================================== Included for Linter =================================== #


def agent_move_and_measure(
    motor_x,
    elem1_x_position,
    elem2_x_position,
    motor_y,
    elem1_y_position,
    elem2_y_position,
    elem1_det_position,
    elem2_det_position,
    *,
    elements=Sequence[str],
    md=None,
    **kwargs,
):
    """
    A complete XAFS measurement for the Cu/Ti sample.
    Each element edge must have it's own calibrated motor positioning and detector distance.
    The sample is moved into position, edge changed and spectra taken.
    Parameters
    ----------
    motor_x :
        Positional motor for sample in x.
    elem1_x_position : float
        Absolute motor position for Cu measurement (This is the real independent variable)
    elem2_x_position : float
        Absolute motor position for Ti measurement
    motor_y :
        Positional motor for sample in y.
    elem1_y_position : float
        Absolute motor position for Cu measurement
    elem2_y_position : float
        Absolute motor position for Ti measurement
    elem1_det_position : float
        Absolute motor position for the xafs detector for the Cu measurement.
    elem2_det_position : float
        Absolute motor position for the xafs detector for the Ti measurement.

    md : Optional[dict]
        Metadata
    kwargs :
        All keyword arguments for the xafs plan. Must include  'filename'. Eg below:
            >>> {'filename': 'Cu_PdCuCr_112421_001',
            >>> 'nscans': 1,
            >>> 'start': 'next',
            >>> 'mode': 'fluorescence',
            >>> 'element': 'Cu',
            >>> 'edge': 'K',
            >>> 'sample': 'PdCuCr',
            >>> 'preparation': 'film deposited on something',
            >>> 'comment': 'index = 1, position (x,y) = (-9.04, -31.64), center at (236.98807533, 80.98291381)',
            >>> 'bounds': '-200 -30 -10 25 12k',
            >>> 'steps': '10 2 0.3 0.05k',
            >>> 'times': '0.5 0.5 0.5 0.5'}
    """

    def elem1_plan():
        yield from bps.mv(motor_x, elem1_x_position)
        _md = {f"{elements[0]}_position": motor_x.position}
        yield from bps.mv(motor_y, elem1_y_position)
        yield from bps.mv(xafs_det, elem1_det_position)
        _md[f"{elements[0]}_det_position"] = xafs_det.position
        _md.update(md or {})
        yield from bps.mv(slits3.vsize, 0.1)
        yield from change_edge(elements[0], focus=True)
        # xafs doesn't take md, so stuff it into a comment string to be ast.literal_eval()
        yield from xafs(element=elements[0], comment=str(_md), **kwargs)

    def elem2_plan():
        yield from bps.mv(motor_x, elem2_x_position)
        _md = {f"{elements[1]}_position": motor_x.position}
        yield from bps.mv(motor_y, elem2_y_position)
        yield from bps.mv(xafs_det, elem2_det_position)
        _md[f"{elements[1]}_det_position"] = xafs_det.position
        _md.update(md or {})
        yield from bps.mv(slits3.vsize, 0.3)
        yield from change_edge(elements[1], focus=True)
        yield from xafs(element=elements[1], comment=str(_md), **kwargs)

    rkvs = redis.Redis(host="xf06bm-ioc2", port=6379, db=0)
    element = rkvs.get("BMM:pds:element").decode("utf-8")
    # edge = rkvs.get('BMM:pds:edge').decode('utf-8')
    if element == elements[1]:
        yield from elem2_plan()
        yield from elem1_plan()
    else:
        yield from elem1_plan()
        yield from elem1_plan()
