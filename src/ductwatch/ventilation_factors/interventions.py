from dataclasses import replace
from statistics import median

from .contracts import VentilationFactors, Proposal


def measure_ventilation_factors(values) -> VentilationFactors:
    pressure_pa, fan_pct, flow_cmh, pm_index, open_pct, since_days = values
    return VentilationFactors(
        flow_per_setting=flow_cmh/fan_pct,
        load_per_open=pressure_pa/(open_pct+10),
        particulates_days=pm_index*since_days,
        scaled_pa=pressure_pa/275,
        restricted_air=fan_pct*max(0,48-open_pct)/80,
        pressure_per_month=pressure_pa/max(1,since_days/30),
        nominal_shortfall=max(0,fan_pct*27-flow_cmh),
        fan_headroom=95-fan_pct,
    )


def propose_filter_inspection(values, missing=()):
    pressure_pa, fan_pct, flow_cmh, pm_index, open_pct, since_days = values
    if 'open_pct' not in missing and (open_pct<=83):
        yield Proposal('打开回风阀十二档', 'open_pct', open_pct, min(95,open_pct+12), 1)
    if 'pressure_pa' not in missing and (pressure_pa>=49):
        yield Proposal('降压后重测滤网', 'pressure_pa', pressure_pa, max(14,pressure_pa-35), 2)
    if 'since_days' not in missing and (since_days>=95):
        yield Proposal('新滤网工况对照', 'since_days', since_days, 3, 3)
    if 'flow_cmh' not in missing and (flow_cmh<=3350):
        yield Proposal('同档复标提高送风量', 'flow_cmh', flow_cmh, min(3600,flow_cmh+250), 2)
