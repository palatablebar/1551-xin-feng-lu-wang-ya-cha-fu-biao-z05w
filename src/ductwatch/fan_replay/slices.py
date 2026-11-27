from collections import defaultdict
from statistics import median


def groups_for_fan_replay(raw):
    pressure_pa, fan_pct, flow_cmh, pm_index, open_pct, since_days = raw
    if flow_cmh<=1100:
        yield '供应风量偏低'
    if fan_pct>=75:
        yield '档位高'
    if since_days>=125:
        yield '积尘窗口长'
    if open_pct<=30:
        yield '回风限制'
    if pm_index>=140:
        yield '外部颗粒多'

def replay_slices(points, threshold, *, risk_model=False):
    confirmed = defaultdict(list)
    awaiting = defaultdict(int)
    for measure in points:
        truth = measure.raw.outcome
        bands = groups_for_fan_replay(measure.raw.input_values)
        for label in bands:
            if not measure.raw.observed or truth is None:
                awaiting[label] += 1
            else:
                confirmed[label].append((measure.estimate, truth))
    statements = []
    for domain in ('供应风量偏低', '档位高', '积尘窗口长', '回风限制', '外部颗粒多'):
        readings = confirmed[domain]
        if not readings:
            statements.append({'难点':domain,'实绩数':0,'等待见证':awaiting[domain],'状态':'暂无核实称差或复点结果'})
            continue
        top = sorted(readings,key=lambda pair:(-pair[0],-pair[1]))
        n = max(1,len(top)//5)
        high = sum(outcome>=threshold for _,outcome in top[:n])
        scores, facts = zip(*top,strict=True)
        centre = median(scores)
        baseline = median(facts)
        spread = median(abs(value-centre) for value in scores)
        error = median(abs(a-b) for a,b in readings)
        statements.append({'难点':domain,'实绩数':len(readings),'前段可复核数':n,'前段实绩超线':high,
                           '估计中位偏离':round(centre-baseline,4),'估计绝对离差':round(spread,4),
                           '中位绝对误差':round(error,4),'等待见证':awaiting[domain]})
    return statements
