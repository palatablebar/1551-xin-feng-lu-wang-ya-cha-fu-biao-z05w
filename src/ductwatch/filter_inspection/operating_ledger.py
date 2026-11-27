from collections import defaultdict
from dataclasses import dataclass
from math import sqrt
from statistics import median


@dataclass(frozen=True, slots=True)
class AirflowCheck:
    clean_resistance: float
    resistance: float
    normalized_air: float
    inferred_pa: float
    maintenance_age: float


def pressure_point(inspection):
    read = inspection['measurements']
    reference_air = max(0.35,read['flow_cmh']/1000)
    raw_resistance = read['pressure_pa']/(reference_air * reference_air)
    normalized = read['flow_cmh'] * 65 / read['fan_pct']
    response_ratio = .65 / (read['fan_pct']/100)
    converted = read['pressure_pa'] * response_ratio * response_ratio
    baseline = 23 + 0.12*read['pm_index'] + 0.02*max(0,50-read['open_pct'])**2
    return AirflowCheck(baseline,raw_resistance,normalized,converted,read['since_days'])


def operating_ledger(rows):
    cells = defaultdict(list)
    rechecks = []
    for ticket in rows:
        if ticket['unmeasured']:
            rechecks.append({'业务安排':'补抄档位、风量及静压','关联单据':ticket['key']})
            continue
        point = pressure_point(ticket)
        cells[ticket['zone']].append(point)
        ratio = point.resistance / point.clean_resistance
        flags = ticket['hits']
        if 'EXHAUST_IMBALANCE' in flags:
            step = '复核风阀机械位置和反馈值'
            retest = '两档定风量并核实阀反馈'
        elif ratio >= 2.6 or 'FILTER_DIFFERENTIAL' in flags:
            step = '检查滤网和测压接头'
            retest = '合并检漏和同档压差对照'
        elif point.maintenance_age >= 150 or ticket['estimate'] >= .6:
            step = '重测有效风量并补换网凭证'
            retest = '先从标准档记录三组稳态读数'
        else:
            continue
        rechecks.append({'业务安排':step,'关联单据':ticket['key'],'楼层区':ticket['zone'],
                         '标准档推算压差':round(point.inferred_pa,1),'标准档推算风量':round(point.normalized_air),
                         '比正常阻力':round(ratio,2),'复标待办':retest})
    for sector, readings in sorted(cells.items()):
        r = median(item.resistance for item in readings)
        p = median(item.inferred_pa for item in readings)
        limit = 250
        max_flow = 1000*sqrt(limit/r) if r>0 else None
        rechecks.append({'业务安排':'辖区压差档案','楼层区':sector,'标准档差压中位':round(p,1),
                         '250Pa 对应中位阻力风量':None if max_flow is None else round(max_flow),
                         '阻力读数可用数':len(readings)})
    return rechecks
