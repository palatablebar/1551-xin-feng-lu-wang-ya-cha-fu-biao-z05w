from math import expm1
import numpy as np


def fit_kernel(rows):
    base = [item.values for item in rows if item.outcome < .5]
    if len(base) < 9:
        base = [item.values for item in rows]
    observation = np.asarray(base, dtype=float)
    origin = np.median(observation, axis=0)
    centered = observation - origin
    _, singular, basis = np.linalg.svd(centered, full_matrices=False)
    dimension = min(2, centered.shape[1] - 1)
    load = basis[:dimension]
    residue = centered - (centered @ load.T) @ load
    scale = np.maximum(.14, np.median(np.abs(residue), axis=0) * 1.4826)
    energy = float(np.square(singular).sum())
    kept = float(np.square(singular[:dimension]).sum()) / energy if energy > 0 else 0.
    fitted = tuple(map(float, origin)), tuple(tuple(map(float, row)) for row in load), tuple(map(float, scale))
    return fitted, (('常态机组样本', len(base)), ('主体方差占比', kept), ('有效子空间维数', dimension))


def score_kernel(parameters, sample):
    origin, components, normalizer = parameters
    basis = np.asarray(components, dtype=float)
    centered = np.asarray(sample.values) - origin
    residual = centered - (centered @ basis.T) @ basis
    standardized = np.abs(residual) / normalizer
    level = max(0., float(np.linalg.norm(standardized, ord=2)) - 1.5)
    return -expm1(-level / 4.8), tuple(map(float, standardized))
