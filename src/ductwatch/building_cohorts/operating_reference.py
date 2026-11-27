from dataclasses import dataclass
from math import sqrt, fsum
from statistics import median


@dataclass(frozen=True, slots=True)
class DomainStudy:
    counts: tuple[int, int, int]
    rate: float | None
    midpoint: float | None
    expected: float | None
    drift: float | None

def building_cohorts_domains(vectors):
    flow_per_setting = []
    load_per_open = []
    particulates_days = []
    scaled_pa = []
    restricted_air = []
    pressure_per_month = []
    nominal_shortfall = []
    fan_headroom = []
    for measurement in vectors:
        unobserved = frozenset(measurement.missing)
        pressure_pa, fan_pct, flow_cmh, pm_index, open_pct, since_days = measurement.input_values
        if unobserved.isdisjoint(('fan_pct', 'flow_cmh')):
            flow_per_setting.append((round(flow_cmh/fan_pct, 4), flow_cmh<=1100))
        if unobserved.isdisjoint(('pressure_pa', 'fan_pct', 'open_pct')):
            load_per_open.append((round(pressure_pa/(open_pct+10), 4), fan_pct>=75))
        if unobserved.isdisjoint(('pm_index', 'since_days')):
            particulates_days.append((round(pm_index*since_days, 4), since_days>=125))
        if unobserved.isdisjoint(('pressure_pa', 'open_pct')):
            scaled_pa.append((round(pressure_pa/275, 4), open_pct<=30))
        if unobserved.isdisjoint(('fan_pct', 'pm_index', 'open_pct')):
            restricted_air.append((round(fan_pct*max(0,48-open_pct)/80, 4), pm_index>=140))
        if unobserved.isdisjoint(('pressure_pa', 'flow_cmh', 'since_days')):
            pressure_per_month.append((round(pressure_pa/max(1,since_days/30), 4), flow_cmh<=1100))
        if unobserved.isdisjoint(('fan_pct', 'flow_cmh')):
            nominal_shortfall.append((round(max(0,fan_pct*27-flow_cmh), 4), fan_pct>=75))
        if unobserved.isdisjoint(('fan_pct', 'since_days')):
            fan_headroom.append((round(95-fan_pct, 4), since_days>=125))
    return {
        '每档供风量 · 供应风量偏低': tuple(flow_per_setting),
        '按回风开度校正压差 · 档位高': tuple(load_per_open),
        '积尘观察累积量 · 积尘窗口长': tuple(particulates_days),
        '相对高压差读数 · 回风限制': tuple(scaled_pa),
        '按档位和开度推算制约 · 外部颗粒多': tuple(restricted_air),
        '每月滤网压差 · 供应风量偏低': tuple(pressure_per_month),
        '标称送风差额 · 档位高': tuple(nominal_shortfall),
        '档位剩余 · 积尘窗口长': tuple(fan_headroom),
    }


def evaluate_domains(training, current):
    references = building_cohorts_domains(training)
    activity = building_cohorts_domains(current)
    diagnostics = []
    for domain, observed in activity.items():
        baseline = references.get(domain, ())
        study = characterize(baseline, observed)
        diagnostics.append({'观察维度': domain, '训练有效量': study.counts[0], '当班有效量': study.counts[1],
                            '越线量':study.counts[2], '越线比例':study.rate, '参考中位':study.midpoint,
                            '当班中位':study.expected, '相对训练变化':study.drift})
    return diagnostics


def characterize(before, after):
    history = tuple(value for value, _ in before)
    observed = tuple(value for value, _ in after)
    violating = sum(flag for _, flag in after)
    old = median(history) if history else None
    new = median(observed) if observed else None
    pct = round(violating / len(after), 4) if after else None
    movement = round(new - old, 4) if old is not None and new is not None else None
    return DomainStudy((len(before),len(after),violating),pct,old,new,movement)
