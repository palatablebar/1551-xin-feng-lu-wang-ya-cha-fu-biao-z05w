from dataclasses import replace
from pathlib import Path
import json

import pytest

from ductwatch.pipeline import open_fixture, execute, preview
from ductwatch.entry import app
from ductwatch.duct_checklists.service import load_samples
from ductwatch.duct_checklists.contracts import DuctwatchRecord
from ductwatch.pressure_epochs.service import build_windows
from ductwatch.ventilation_factors.service import fit_features, transform_windows, transform
from ductwatch.flow_subspace.service import fit_model, predict, predict_one
from ductwatch.fan_replay.service import prepare_verification
from ductwatch.filter_inspection.contracts import Job, Plan
from ductwatch.hvac_reconciliation.contracts import ReferenceBand
from ductwatch.hvac_reconciliation.settlement import (
    build_reference, settle, standard_gear_values, MIN_REFERENCE)

RECEIPTS_FILE = Path(__file__).resolve().parents[1] / 'sample_data' / 'filter_receipts_sample.json'


def receipt(key, pa, fan, flow, pm=60.0, op=70.0, days=4.0, day=97, received=97, revision=1):
    return {'key': key, 'day': day, 'received': received, 'revision': revision,
            'pressure_pa': pa, 'fan_pct': fan, 'flow_cmh': flow,
            'pm_index': pm, 'open_pct': op, 'since_days': days}


def plan_for(*keys, cost=2):
    jobs = tuple(Job(key, '地下机房', 0.05, None, None, cost, '已分派', 'EXHAUST_IMBALANCE', 'x', 0.9, ())
                 for key in keys)
    used = cost * len(keys)
    return Plan(jobs, 12, 12 - used, (('地下机房', used),))


@pytest.fixture(scope='module')
def chain():
    sample = open_fixture()
    intake = load_samples(sample['records'], sample['as_of'])
    windows = build_windows(intake.entries)
    state = fit_features(windows.train)
    features = transform_windows(windows, state)
    kernel = fit_model(features.train, state.fingerprint)
    verification = prepare_verification(predict(kernel, features.calibration, state.fingerprint))
    reference = build_reference(windows, state, kernel, verification)
    return windows, state, kernel, verification, reference


def run_settle(chain, plan, receipts, reference=None, stamp='test-dispatch'):
    _, state, kernel, verification, frozen = chain
    return settle(plan, receipts, reference or frozen, state, kernel, verification, stamp)


def decision_of(voucher, key):
    return next(item for item in voucher.decisions if item.key == key)


def test_clean_replacement_settles_and_releases_workstation(chain):
    # 派单时风机 83%，换网实测在 52% 档：不等回原档也能核销
    voucher = run_settle(chain, plan_for('AF-1'), [receipt('AF-1', 77, 52, 1120, pm=58, op=68)])
    decision = decision_of(voucher, 'AF-1')
    assert decision.decision == '销单' and decision.reason == 'SETTLED'
    assert voucher.released == 2 and voucher.held == 0 and voucher.occupied == 2
    assert decision.receipt_score <= voucher.reference.fence
    assert decision.receipt_fingerprint


def test_gear_shift_is_not_mistaken_for_filter_effect(chain):
    # 滤网仍脏但风机降档：直接比分像降险，换算标准档后仍超参照
    _, state, kernel, verification, reference = chain
    voucher = run_settle(chain, plan_for('AF-1'), [receipt('AF-1', 164, 48, 812)])
    decision = decision_of(voucher, 'AF-1')
    assert decision.decision == '占位' and decision.reason == 'RISK_UNRESOLVED'
    assert decision.receipt_score > voucher.reference.fence
    probe = DuctwatchRecord('AF-1', '地下机房', 97, 97, 1, None, None, True, 164, 48, 812, 60, 70, 4)
    direct = predict_one(kernel, transform(probe, state)).score
    assert direct < voucher.reference.fence  # 直接比分会把换档误认成换网成效
    assert voucher.released == 0 and voucher.held == 2


def test_clean_receipt_is_gear_invariant(chain):
    plan = plan_for('AF-1')
    vouchers = [run_settle(chain, plan, [receipt('AF-1', pa, fan, flow, pm=58, op=68)])
                for pa, fan, flow in ((57.5, 45, 969.2), (76.8, 52, 1120.0), (120.0, 65, 1400.0), (181.8, 80, 1723.1))]
    assert all(item.decisions[0].decision == '销单' for item in vouchers)
    scores = {item.decisions[0].receipt_score for item in vouchers}
    assert max(scores) - min(scores) < 0.01


def test_pause_rule_blocks_settlement_even_when_risk_drops(chain):
    # 实测命中暂停规则：换算后分数在参照内也不销单
    voucher = run_settle(chain, plan_for('AF-1'), [receipt('AF-1', 280, 90, 1150, pm=50, op=75)])
    decision = decision_of(voucher, 'AF-1')
    assert decision.decision == '占位' and decision.reason == 'MEASUREMENT_PAUSE'
    assert decision.receipt_score <= voucher.reference.fence  # 即便降险也不销单
    assert voucher.released == 0


def test_missing_measurement_keeps_slot(chain):
    voucher = run_settle(chain, plan_for('AF-1'),
                         [receipt('AF-1', 80, 55, None, pm=55, op=65)])
    decision = decision_of(voucher, 'AF-1')
    assert decision.decision == '占位' and decision.reason == 'MEASUREMENT_INCOMPLETE'
    assert 'flow_cmh' in decision.summary
    assert voucher.released == 0


def test_conflicting_same_version_receipts_keep_slot(chain):
    pair = [receipt('AF-1', 90, 58, 1250, op=66, days=5),
            receipt('AF-1', 140, 58, 1250, op=66, days=5, received=98)]
    voucher = run_settle(chain, plan_for('AF-1'), pair)
    assert decision_of(voucher, 'AF-1').reason == 'RECEIPT_CONFLICT'
    assert voucher.released == 0 and voucher.held == 2


def test_awaiting_receipt_keeps_slot(chain):
    voucher = run_settle(chain, plan_for('AF-1', 'AF-2'), [receipt('AF-1', 77, 52, 1120, pm=58, op=68)])
    assert decision_of(voucher, 'AF-2').reason == 'AWAITING_RECEIPT'
    assert voucher.released == 2 and voucher.held == 2 and voucher.occupied == 4


def test_newer_revision_wins_regardless_of_arrival_order(chain):
    old = receipt('AF-1', 77, 52, 1120, pm=58, op=68, revision=1)          # 干净，可销单
    new = receipt('AF-1', 164, 48, 812, revision=2, received=98)           # 更正后仍脏
    forward = run_settle(chain, plan_for('AF-1'), [old, new])
    backward = run_settle(chain, plan_for('AF-1'), [new, old])
    assert forward.stamp == backward.stamp
    assert decision_of(forward, 'AF-1').reason == 'RISK_UNRESOLVED'
    assert forward.superseded_receipts == 1 and forward.released == 0


def test_replay_out_of_order_never_releases_twice(chain):
    plan = plan_for('AF-1', 'AF-2')
    receipts = [receipt('AF-1', 77, 52, 1120, pm=58, op=68),
                receipt('AF-2', 120, 65, 1400, pm=58, op=68)]
    first = run_settle(chain, plan, receipts)
    replayed = run_settle(chain, plan, list(reversed(receipts)))
    duplicated = run_settle(chain, plan, receipts + receipts)
    assert first.stamp == replayed.stamp == duplicated.stamp
    assert first.released == replayed.released == duplicated.released == 4
    assert duplicated.decisions == first.decisions
    assert duplicated.duplicate_receipts == 2 and first.duplicate_receipts == 0


def test_late_confirmed_record_not_added_to_reference(chain):
    _, state, kernel, verification, reference = chain
    sample = open_fixture()
    late_mature = [dict(row) for row in sample['records']]
    late_mature.append({'key': 'AF-LATE', 'cohort': '地下机房', 'day': 30, 'received': 30,
                        'result_day': 45, 'outcome': 0, 'pressure_pa': 120, 'fan_pct': 65,
                        'flow_cmh': 1400, 'pm_index': 60, 'open_pct': 70, 'since_days': 40})
    late_arrival = [dict(row) for row in sample['records']]
    late_arrival.append({'key': 'AF-SLOW', 'cohort': '地下机房', 'day': 30, 'received': 97,
                         'result_day': 33, 'outcome': 0, 'pressure_pa': 120, 'fan_pct': 65,
                         'flow_cmh': 1400, 'pm_index': 60, 'open_pct': 70, 'since_days': 40})
    for records in (late_mature, late_arrival):
        intake = load_samples(records, sample['as_of'])
        windows = build_windows(intake.entries)
        rebuilt = build_reference(windows, state, kernel, verification)
        assert rebuilt.fingerprint == reference.fingerprint
        assert rebuilt.count == reference.count


def test_sparse_reference_keeps_all_slots(chain):
    windows, state, kernel, verification, _ = chain
    sparse = replace(windows, train=windows.train[:2], calibration=(), replay=())
    reference = build_reference(sparse, state, kernel, verification)
    assert not reference.usable and reference.count < MIN_REFERENCE
    voucher = run_settle(chain, plan_for('AF-1'), [receipt('AF-1', 77, 52, 1120, pm=58, op=68)],
                       reference=reference)
    assert decision_of(voucher, 'AF-1').reason == 'REFERENCE_SPARSE'
    assert voucher.released == 0


def test_converted_measurement_out_of_envelope_keeps_slot(chain):
    # 参照上限放宽时，换算后超出训练参照域仍属证据不足
    loose = ReferenceBand((55.0, 75.0), 54, 0.13, 99.0, 'loose', True)
    voucher = run_settle(chain, plan_for('AF-1'), [receipt('AF-1', 164, 48, 812)], reference=loose)
    decision = decision_of(voucher, 'AF-1')
    assert decision.reason == 'OUT_OF_REFERENCE'
    assert decision.receipt_score < loose.fence


def test_unknown_order_receipt_isolated(chain):
    voucher = run_settle(chain, plan_for('AF-1'),
                         [receipt('AF-1', 77, 52, 1120, pm=58, op=68), receipt('AF-X', 77, 52, 1120)])
    assert [issue.code for issue in voucher.issues] == ['ORDER_NOT_DISPATCHED']
    assert voucher.issues[0].key == 'AF-X'
    assert voucher.released == 2 and voucher.occupied == 2


def test_voucher_conservation_is_enforced(chain):
    _, state, kernel, verification, reference = chain
    voucher = run_settle(chain, plan_for('AF-1'), [receipt('AF-1', 77, 52, 1120, pm=58, op=68)])
    with pytest.raises(ArithmeticError, match='不守恒'):
        replace(voucher, occupied=99)
    with pytest.raises(ArithmeticError, match='汇总'):
        replace(voucher, decisions=(replace(voucher.decisions[0], cost=5),))


def test_voucher_stamp_tracks_measurement_and_reference(chain):
    plan = plan_for('AF-1')
    base = run_settle(chain, plan, [receipt('AF-1', 77, 52, 1120, pm=58, op=68)])
    changed = run_settle(chain, plan, [receipt('AF-1', 78, 52, 1120, pm=58, op=68)])
    other_dispatch = run_settle(chain, plan, [receipt('AF-1', 77, 52, 1120, pm=58, op=68)], stamp='other')
    assert base.stamp != changed.stamp
    assert base.stamp != other_dispatch.stamp
    assert base.reference.fingerprint == changed.reference.fingerprint


def test_standard_gear_conversion_excludes_fan_effect():
    assert standard_gear_values((120.0, 65.0, 1400.0, 60.0, 70.0, 4.0)) == (120.0, 65.0, 1400.0, 60.0, 70.0, 4.0)
    pa, fan, flow, *_ = standard_gear_values((76.8, 52.0, 1120.0, 58.0, 68.0, 4.0))
    assert round(pa, 1) == 120.0 and fan == 65.0 and round(flow, 1) == 1400.0


def test_pipeline_settles_without_changing_dispatch():
    sample = open_fixture()
    receipts = json.loads(RECEIPTS_FILE.read_text(encoding='utf-8'))['receipts']
    base = execute(sample['records'])
    settled = execute(sample['records'], receipts=receipts)
    assert settled['run_id'] == base['run_id']  # 回执不进入派单批次
    assert len(settled['sections']) == 8
    assert base['settlement'] is None
    block = settled['settlement']
    assert block['dispatch_stamp'] == settled['run_id']
    assert block['feature_stamp'] == settled['feature_stamp']
    totals = block['totals']
    dispatched_cost = sum(row['cost'] for row in settled['rows'] if row['state'] == '已分派')
    assert totals['派单工位'] == dispatched_cost == totals['已释放'] + totals['仍占位']
    reasons = {row['单号']: row['原因码'] for row in block['decisions']}
    assert reasons == {'AF-1253': 'SETTLED', 'AF-1254': 'RISK_UNRESOLVED', 'AF-1256': 'MEASUREMENT_PAUSE',
                       'AF-1262': 'MEASUREMENT_INCOMPLETE', 'AF-1273': 'RECEIPT_CONFLICT',
                       'AF-RECHECK': 'AWAITING_RECEIPT'}
    assert totals['销单'] == 1 and totals['已释放'] == 2
    assert [issue['原因'] for issue in block['issues']] == ['ORDER_NOT_DISPATCHED']


def test_pipeline_settlement_is_replay_safe():
    sample = open_fixture()
    receipts = json.loads(RECEIPTS_FILE.read_text(encoding='utf-8'))['receipts']
    first = execute(sample['records'], receipts=receipts)['settlement']
    reordered = execute(sample['records'], receipts=list(reversed(receipts)))['settlement']
    duplicated = execute(sample['records'], receipts=receipts + receipts)['settlement']
    assert first['stamp'] == reordered['stamp'] == duplicated['stamp']
    assert first['decisions'] == duplicated['decisions']
    assert first['totals']['已释放'] == duplicated['totals']['已释放']


def test_api_accepts_receipts_and_validates_batch():
    client = app.test_client()
    receipts = json.loads(RECEIPTS_FILE.read_text(encoding='utf-8'))['receipts']
    payload = open_fixture()
    payload['receipts'] = receipts
    response = client.post('/api/ductwatch/run', json=payload)
    assert response.status_code == 200
    assert response.get_json()['settlement']['totals']['销单'] == 1
    preset = client.post('/api/ductwatch/run', json={'receipts': receipts})
    assert preset.status_code == 200 and preset.get_json()['settlement'] is not None
    bad = client.post('/api/ductwatch/run', json={'receipts': 'not-a-list'})
    assert bad.status_code == 422


def test_preview_without_receipts_has_no_settlement():
    assert preview()['settlement'] is None
