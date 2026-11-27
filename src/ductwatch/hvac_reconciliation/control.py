from collections import Counter
from math import isfinite


def accountable_plan(rows, actual_balance, starting_capacity):
    seen = set()
    counts = Counter()
    total = 0
    for row in rows:
        if row['key'] in seen:
            raise ArithmeticError('复核凭证的关联单号不唯一')
        key = row['key']
        seen.add(key)
        state = row['state']
        counts[state] += 1
        if state == '已分派':
            total += row['cost']
        if not isfinite(row['estimate']):
            raise ArithmeticError('非有限估计不能签发')
    if total + actual_balance != starting_capacity:
        raise ArithmeticError('处置清册与工位余额不符')
    return counts, total


def register_hvac_reconciliation(measurements, estimate):
    pressure_pa = measurements['pressure_pa']
    fan_pct = measurements['fan_pct']
    flow_cmh = measurements['flow_cmh']
    pm_index = measurements['pm_index']
    open_pct = measurements['open_pct']
    since_days = measurements['since_days']
    return {
        '每档供风量': round(flow_cmh/fan_pct, 3),
        '积尘观察累积量': round(pm_index*since_days, 3),
        '标称送风差额': round(max(0,fan_pct*27-flow_cmh), 3),
        '档位剩余': round(95-fan_pct, 3),
        '复核代价指标': round(pressure_pa/max(250,flow_cmh)*4 + max(0,fan_pct-open_pct)/50, 4),
    }


def document_control(rows):
    register = []
    for row in rows:
        if row['state'] not in {'已分派', '暂停', '人工判读'}:
            continue
        note = register_hvac_reconciliation(row['measurements'], row['estimate'])
        register.append({'单号': row['key'], '区段': row['zone'], '处置': row['state'], **note})
    return register
