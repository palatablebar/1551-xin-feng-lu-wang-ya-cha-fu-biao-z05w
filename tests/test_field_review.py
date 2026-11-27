from ductwatch.pipeline import preview
from ductwatch.filter_inspection.service import operating_ledger


def note(key, measures, *, zone='甲区', state='已分派', estimate=0, hits=(), missing=()):
    return {'key':key,'zone':zone,'state':state,'estimate':estimate,'hits':hits,
            'unmeasured':missing,'measurements':dict(zip(('pressure_pa', 'fan_pct', 'flow_cmh', 'pm_index', 'open_pct', 'since_days'),measures,strict=True))}


def test_field_plan_is_visible_and_references_real_tickets():
    desk = preview()
    plan = desk['sections'][6]
    assert plan['operating_title'] == '标准档复标单'
    assert plan['operating_rows']
    scoped = {item['关联单据'] for item in plan['operating_rows'] if '关联单据' in item}
    assert scoped and scoped <= {row['key'] for row in desk['rows']}
    assert all(item['业务安排'] for item in plan['operating_rows'])


def test_valve_feedback_is_required_before_filter_replacement_review():
    damper = note('AF-1',(240,86,1750,40,12,72),estimate=.8,hits=('EXHAUST_IMBALANCE',))
    alert, sector = operating_ledger([damper])
    assert alert['业务安排']=='复核风阀机械位置和反馈值'
    assert alert['标准档推算风量']<1750
    assert sector['阻力读数可用数']==1
