from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class JointAction:
    case: str
    work_units: int
    notes: str
    changes: dict[str, tuple[float, float]]

    def evidence(self, old_value, new_value, extrapolates):
        return {'联动推演':self.case, '用量':self.work_units, '先决条件':self.notes,
                '原预测':round(old_value,4), '替换预测':round(new_value,4),
                '变化':round(new_value-old_value,4), '超训练域':bool(extrapolates),
                '联动量测':{item:{'原值':before,'替换值':after} for item,(before,after) in self.changes.items()}}


def simulate_recover_airflow(readings, invalid):
    flow_cmh, open_pct = readings[2], readings[4]
    if invalid.intersection(('flow_cmh', 'open_pct')):
        return None
    if not (open_pct<=82 and flow_cmh<=3250):
        return None
    open_pct_adjusted = open_pct+12
    flow_cmh_adjusted = flow_cmh+340
    inspected = {
        'open_pct': (open_pct, open_pct_adjusted),
        'flow_cmh': (flow_cmh, flow_cmh_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('同档模拟开阀加供风', 2, '回风阀回位后检查流量反馈', inspected)
    return None


def simulate_recalibrate_fan(readings, invalid):
    pressure_pa, fan_pct = readings[0], readings[1]
    if invalid.intersection(('pressure_pa', 'fan_pct')):
        return None
    if not (pressure_pa>=75 and fan_pct>=37):
        return None
    pressure_pa_adjusted = pressure_pa-35
    fan_pct_adjusted = fan_pct-17
    inspected = {
        'pressure_pa': (pressure_pa, pressure_pa_adjusted),
        'fan_pct': (fan_pct, fan_pct_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('标定档压差同步校正', 2, '记录降档后两块表读数', inspected)
    return None


def simulate_install_filter_test(readings, invalid):
    pressure_pa, since_days = readings[0], readings[5]
    if invalid.intersection(('pressure_pa', 'since_days')):
        return None
    if not (since_days>=24 and pressure_pa>=51):
        return None
    since_days_adjusted = 3
    pressure_pa_adjusted = pressure_pa-28
    inspected = {
        'since_days': (since_days, since_days_adjusted),
        'pressure_pa': (pressure_pa, pressure_pa_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('新滤材替换盘点', 3, '留存更换后高低位压差', inspected)
    return None


def simulate_separate_intake(readings, invalid):
    pm_index, open_pct = readings[3], readings[4]
    if invalid.intersection(('pm_index', 'open_pct')):
        return None
    if not (open_pct<=87 and pm_index>=34):
        return None
    open_pct_adjusted = open_pct+8
    pm_index_adjusted = pm_index-26
    inspected = {
        'open_pct': (open_pct, open_pct_adjusted),
        'pm_index': (pm_index, pm_index_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('开回风改善外部暴露', 2, '切换进风路线后核对颗粒计', inspected)
    return None


def simulate_tune_delivery(readings, invalid):
    fan_pct, flow_cmh = readings[1], readings[2]
    if invalid.intersection(('fan_pct', 'flow_cmh')):
        return None
    if not (flow_cmh<=3200 and fan_pct<=85):
        return None
    flow_cmh_adjusted = flow_cmh+250
    fan_pct_adjusted = fan_pct+7
    inspected = {
        'flow_cmh': (flow_cmh, flow_cmh_adjusted),
        'fan_pct': (fan_pct, fan_pct_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('风量校正档位', 2, '在同风道验算压差-风量交互', inspected)
    return None


def options(values, missing):
    measurements=tuple(values)
    unobserved=frozenset(missing)
    cases=(
        simulate_recover_airflow(measurements, unobserved),
        simulate_recalibrate_fan(measurements, unobserved),
        simulate_install_filter_test(measurements, unobserved),
        simulate_separate_intake(measurements, unobserved),
        simulate_tune_delivery(measurements, unobserved),
    )
    return tuple(action for action in cases if action is not None)
