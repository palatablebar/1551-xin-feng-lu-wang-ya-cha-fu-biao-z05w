from math import exp, log, fsum, sqrt
from statistics import median, mean, quantiles

from .pca_model import score_kernel



def explain_flow_subspace(fit, calibration, replay, live):
    location, basis, dispersion = fit.parameters
    coordinates = ('阻力','风量','积尘','回风','换网龄期')
    checks = []
    for coordinate, unit in enumerate(coordinates):
        strength = sum(axis[coordinate]**2 for axis in basis)
        checks.append({'新风分量':unit,'复原子空间载荷':round(strength,4), '残差阈尺度':round(dispersion[coordinate],4),
                       '常态中心':round(location[coordinate], 3)})
    for equipment in sorted(live,key=lambda fan:-fan.input_values[0])[:5]:
        score, deviations = score_kernel(fit.parameters,equipment)
        driver = max(range(len(deviations)),key=deviations.__getitem__)
        checks.append({'机组':equipment.key,'复标分量':coordinates[driver],'残差强度':round(deviations[driver],4),
                       '机组异动':round(score,4)})
    return checks
