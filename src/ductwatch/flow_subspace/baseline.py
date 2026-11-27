from collections import defaultdict
from math import fabs, fsum
from statistics import mean, median

from .pca_model import score_kernel


def mechanical_bounds(previous):
    baseline = [item.input_values[0]/(1+(item.input_values[2]/1100)**2) for item in previous if item.outcome==0]
    nominal = median(baseline) if baseline else 88.
    return nominal, max(18,median(abs(val-nominal) for val in baseline)) if baseline else 22.


def rated_pressure(limits,unit):
    center, bandwidth=limits
    pressure, _, airflow, *_ = unit.input_values
    normalized=pressure/(1+(airflow/1100)**2)
    return max(0.,min(1,(normalized-center)/(6*bandwidth)))


def baseline_review(fit, training, replay):
    regular_load = mechanical_bounds(training)
    matched = defaultdict(lambda: [[],[]])
    for sample in replay:
        if sample.outcome is None or not sample.observed:
            continue
        measured, _ = score_kernel(fit.parameters,sample)
        normal = rated_pressure(regular_load, sample)
        bucket = int(sample.outcome >= 0.6)
        matched[sample.cohort][bucket].append((fabs(sample.outcome-measured),fabs(sample.outcome-normal),measured,normal))
    readings = []
    for lane, (ordinary, flagged) in sorted(matched.items()):
        series = ordinary + flagged
        average = mean(row[0] for row in series)
        conventional = mean(row[1] for row in series)
        crossings = [row for row in ordinary if row[2]>=0.6]
        detection = sum(row[2]>=0.6 for row in flagged)
        readings.append({'回放组':lane,'实绩数':len(series),'基线':'额定风量下的人工压差线',
                         '估计代价':round(average,4),'业务基线代价':round(conventional,4),
                         '已证异常':len(flagged),'覆盖异常':detection,'正常件误报':len(crossings),
                         '正常件误报率':round(len(crossings)/len(ordinary),4) if ordinary else None})
    return readings
