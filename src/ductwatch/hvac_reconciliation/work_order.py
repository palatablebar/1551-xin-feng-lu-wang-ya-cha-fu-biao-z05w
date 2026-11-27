def collect_filter_diff(measures, missing, estimate):
    pressure_pa = measures['pressure_pa']
    if not (pressure_pa>=170):
        return None
    value=pressure_pa
    return {'现场复核':'标压差','可复查值':round(value,3),'单位':'Pa','归档要求':'同转速用第二块表复核',
            '需补测':not set(missing).isdisjoint(('pressure_pa',))}


def collect_motor_review(measures, missing, estimate):
    fan_pct = measures['fan_pct']
    if not (fan_pct>=68):
        return None
    value=fan_pct
    return {'现场复核':'对齐风机转速','可复查值':round(value,3),'单位':'%','归档要求':'停机前留工控设备档值',
            '需补测':not set(missing).isdisjoint(('fan_pct',))}


def collect_vent_delivery(measures, missing, estimate):
    flow_cmh = measures['flow_cmh']
    open_pct = measures['open_pct']
    if not (flow_cmh<=1250 or open_pct<=27):
        return None
    value=flow_cmh
    return {'现场复核':'风口实测','可复查值':round(value,3),'单位':'m³/h','归档要求':'记录同档回风阀开度',
            '需补测':not set(missing).isdisjoint(('flow_cmh', 'open_pct'))}


def collect_filter_age(measures, missing, estimate):
    since_days = measures['since_days']
    if not (since_days>=104):
        return None
    value=since_days
    return {'现场复核':'滤材领用','可复查值':round(value,3),'单位':'天','归档要求':'追查耗材签单和换网工日',
            '需补测':not set(missing).isdisjoint(('since_days',))}


def check_hvac_reconciliation(records):
    guide = []
    for ticket in records:
        if ticket['state'] not in ('已分派','暂停','人工判读'):
            continue
        measures=ticket['measurements']
        absent=ticket['unmeasured']
        estimate=ticket['estimate']
        checks = (
            collect_filter_diff(measures,absent,estimate),
            collect_motor_review(measures,absent,estimate),
            collect_vent_delivery(measures,absent,estimate),
            collect_filter_age(measures,absent,estimate),
        )
        required=tuple(check for check in checks if check is not None)
        if not required:
            continue
        review=ticket['key']
        for check in required:
            guide.append({'签收单':review,'作业区':ticket['zone'],'处置':ticket['state'],**check})
    return guide
