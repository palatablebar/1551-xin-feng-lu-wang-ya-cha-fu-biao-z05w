"""换网实测核销。

工作台派出的滤网复标单凭换网后的实测回执核销。换网前后沿用派单时冻结的
特征、模型与校准；实测不等风机回原档，也不直接对比前后分数，而是把压差与
风量换算到 65% 标准档后评分，再对照派单时已确认正常实绩的参照上限。证据
不足或有分歧继续占位，实测触发暂停即便降险也不销单。回执乱序或重复重跑
不重复释放工位，核销凭证可回查实测指纹与参照指纹。
"""
from collections.abc import Mapping
from hashlib import blake2s, sha256
from statistics import median
from unicodedata import normalize

from ..duct_checklists.contracts import FIELDS, DuctwatchRecord, Issue, MeasureIssue
from ..duct_checklists.service import number
from ..fan_replay.service import check_point
from ..filter_inspection.service import signals
from ..flow_subspace.service import predict_one
from ..ventilation_factors.contracts import RAW_KEYS
from ..ventilation_factors.service import transform
from .contracts import (ReceiptTicket, ReferenceBand, SettlementDecision, SettlementVoucher)
from .service import emit_bytes

STANDARD_GEAR = 65.0
REFERENCE_GEARS = (55.0, 75.0)
MIN_REFERENCE = 8
FENCE_SCALE = 3.0
ROBUST_Z = 1.4826
RECEIPT_LIMIT = 2500
SETTLED = '销单'
HOLDING = '占位'


def receipt_key(raw):
    if type(raw) is not str:
        raise MeasureIssue('key', 'TEXT_REQUIRED')
    short = normalize('NFKC', raw).strip()
    if not (0 < len(short) <= 64 and short.isprintable()):
        raise MeasureIssue('key', 'TEXT_INVALID')
    return short


def parse_receipt(row, position):
    if not isinstance(row, Mapping):
        raise MeasureIssue('row', 'OBJECT_REQUIRED')
    key = receipt_key(row.get('key'))
    beginning = number(row.get('day'), 'day', 0, 3650, integral=True)
    reached = number(row.get('received'), 'received', beginning, 3650, integral=True)
    revision = number(row.get('revision', 1), 'revision', 1, 1000, integral=True)
    values = []
    missing = []
    for field, (_, _, lower, upper) in FIELDS.items():
        measurement = row.get(field)
        if measurement is None or measurement == '':
            values.append(None)
            missing.append(field)
        else:
            values.append(number(measurement, field, lower, upper))
    values = tuple(values)
    fingerprint = sha256(emit_bytes((key, beginning, revision, values))).hexdigest()
    return ReceiptTicket(key, beginning, reached, revision, position, values, tuple(missing), fingerprint)


def parse_receipts(receipts):
    tickets = []
    issues = []
    for position, row in enumerate(receipts, 1):
        try:
            tickets.append(parse_receipt(row, position))
        except MeasureIssue as problem:
            name = row.get('key', '') if isinstance(row, Mapping) else ''
            issues.append(Issue(position, str(name)[:64], problem.field, problem.code))
    return tickets, issues


def resolve_receipts(tickets):
    """同号取最高版次；同版读数不一致记分歧；完全相同只算一张，重跑不重复生效。"""
    by_key = {}
    for ticket in tickets:
        by_key.setdefault(ticket.key, []).append(ticket)
    effective = {}
    conflicts = set()
    duplicates = 0
    superseded = 0
    for key, group in by_key.items():
        top = max(ticket.revision for ticket in group)
        current = [ticket for ticket in group if ticket.revision == top]
        superseded += len(group) - len(current)
        distinct = {ticket.fingerprint for ticket in current}
        if len(distinct) > 1:
            conflicts.add(key)
            continue
        effective[key] = min(current, key=lambda ticket: ticket.position)
        duplicates += len(current) - 1
    return effective, conflicts, duplicates, superseded


def standard_gear_values(values):
    """把压差和风量换算到 65% 标准档，排除档位影响。"""
    pressure_pa, fan_pct, flow_cmh, pm_index, open_pct, since_days = values
    ratio = STANDARD_GEAR / fan_pct
    return (pressure_pa * ratio * ratio, STANDARD_GEAR, flow_cmh * ratio, pm_index, open_pct, since_days)


def build_reference(windows, feature_state, kernel, verification):
    """只用派单时已确认正常的实绩（量测齐全、档位在参照档窗口内）。"""
    normals = []
    for name, records in windows.partitions():
        if name == 'live':
            continue
        for record in records:
            if record.outcome != 0.0 or not record.observed:
                continue
            values = tuple(getattr(record, field) for field in RAW_KEYS)
            if any(value is None for value in values):
                continue
            if not (REFERENCE_GEARS[0] <= record.fan_pct <= REFERENCE_GEARS[1]):
                continue
            vector = transform(record, feature_state)
            scored = predict_one(kernel, vector)
            estimate = check_point(scored, verification).estimate
            normals.append((record, scored.score, estimate))
    count = len(normals)
    usable = count >= MIN_REFERENCE
    center = fence = None
    if usable:
        scores = [item[1] for item in normals]
        center = median(scores)
        deviation = median([abs(score - center) for score in scores])
        fence = center + FENCE_SCALE * ROBUST_Z * deviation
    rows = sorted((record.key, record.day, record.revision, round(score, 6), round(estimate, 6))
                  for record, score, estimate in normals)
    fingerprint = sha256(emit_bytes(rows)).hexdigest()
    return ReferenceBand(REFERENCE_GEARS, count, center, fence, fingerprint, usable)


def decide(job, ticket, conflict, reference, feature_state, kernel, verification):
    def row(decision, reason, summary, score=None, estimate=None, day=None, revision=None, fingerprint=None):
        return SettlementDecision(job.key, job.cohort, job.cost, decision, reason, summary,
                                  job.estimate, score, estimate, day, revision, fingerprint)

    if conflict:
        return row(HOLDING, 'RECEIPT_CONFLICT', '同版回执读数不一致，存在分歧，工位继续占位')
    if ticket is None:
        return row(HOLDING, 'AWAITING_RECEIPT', '等待换网实测回执，工位继续占位')
    if ticket.missing:
        lack = '、'.join(ticket.missing)
        return row(HOLDING, 'MEASUREMENT_INCOMPLETE', f'回执缺测 {lack}，证据不足，工位继续占位',
                   day=ticket.day, revision=ticket.revision, fingerprint=ticket.fingerprint)
    hits = signals(ticket.values, None, ())
    hard = next((hit for hit in hits if hit.hard), None)
    probe = DuctwatchRecord(job.key, job.cohort, ticket.day, ticket.received, ticket.revision,
                            None, None, True, *standard_gear_values(ticket.values))
    vector = transform(probe, feature_state)
    scored = predict_one(kernel, vector)
    score = round(scored.score, 4)
    estimate = round(check_point(scored, verification).estimate, 4)
    if hard is not None:
        return row(HOLDING, 'MEASUREMENT_PAUSE', f'实测触发暂停规则 {hard.rule_id}，即便降险也不销单',
                   score, estimate, ticket.day, ticket.revision, ticket.fingerprint)
    if not reference.usable:
        return row(HOLDING, 'REFERENCE_SPARSE',
                   f'历史正常实绩仅 {reference.count} 条，证据不足，工位继续占位',
                   score, estimate, ticket.day, ticket.revision, ticket.fingerprint)
    if scored.score > reference.fence:
        return row(HOLDING, 'RISK_UNRESOLVED', '排除档位影响后仍高于历史正常参照，降险未确认，工位继续占位',
                   score, estimate, ticket.day, ticket.revision, ticket.fingerprint)
    if vector.excursions:
        return row(HOLDING, 'OUT_OF_REFERENCE', '标准档换算后超出训练参照域，证据不足，工位继续占位',
                   score, estimate, ticket.day, ticket.revision, ticket.fingerprint)
    return row(SETTLED, 'SETTLED', '换网实测经标准档换算后落在历史正常参照内，确认降险，销单释放工位',
               score, estimate, ticket.day, ticket.revision, ticket.fingerprint)


def settle(plan, receipts, reference, feature_state, kernel, verification, dispatch_stamp):
    tickets, issues = parse_receipts(receipts)
    effective, conflicts, duplicates, superseded = resolve_receipts(tickets)
    dispatched = {job.key: job for job in plan.jobs if job.state == '已分派'}
    decisions = tuple(decide(dispatched[key], effective.get(key), key in conflicts,
                             reference, feature_state, kernel, verification)
                      for key in sorted(dispatched))
    positions = {}
    for ticket in tickets:
        positions[ticket.key] = min(positions.get(ticket.key, ticket.position), ticket.position)
    stray = (set(effective) | set(conflicts)) - set(dispatched)
    issues.extend(Issue(positions[key], key, 'key', 'ORDER_NOT_DISPATCHED') for key in sorted(stray))
    issues.sort(key=lambda issue: (issue.source_row, issue.key))
    occupied = sum(job.cost for job in dispatched.values())
    released = sum(item.cost for item in decisions if item.decision == SETTLED)
    held = occupied - released
    # 凭证只锚定核销结果：回执的到达次序、重复次数与行号不改变核销身份
    payload = (dispatch_stamp, feature_state.fingerprint, kernel.name, kernel.fingerprint,
               verification.method, reference.fingerprint,
               tuple((item.key, item.decision, item.reason, item.cost, item.receipt_score,
                      item.receipt_estimate, item.receipt_fingerprint) for item in decisions),
               tuple(sorted({(issue.key, issue.field, issue.code) for issue in issues})),
               (occupied, released, held))
    stamp = blake2s(emit_bytes(payload), digest_size=8).hexdigest()
    return SettlementVoucher(stamp, dispatch_stamp, feature_state.fingerprint, kernel.name,
                             kernel.fingerprint, verification.method, reference, decisions,
                             tuple(issues), occupied, released, held,
                             len(effective), duplicates, superseded)


def decision_rows(voucher):
    fence = voucher.reference.fence
    rows = []
    for item in voucher.decisions:
        rows.append({'单号': item.key, '作业区': item.cohort, '核销': item.decision, '原因码': item.reason,
                     '依据': item.summary, '工位': item.cost, '派单估值': item.dispatch_estimate,
                     '实测分': item.receipt_score, '实测估值': item.receipt_estimate,
                     '参照上限': None if fence is None else round(fence, 4),
                     '回执日': item.receipt_day, '回执版次': item.receipt_revision,
                     '回执指纹': None if item.receipt_fingerprint is None else item.receipt_fingerprint[:12]})
    return rows


def settlement_evidence(voucher):
    reference = voucher.reference
    settled = sum(item.decision == SETTLED for item in voucher.decisions)
    holding = len(voucher.decisions) - settled
    return {'stamp': voucher.stamp, 'dispatch_stamp': voucher.dispatch_stamp,
            'feature_stamp': voucher.feature_stamp, 'model': voucher.model,
            'model_fingerprint': voucher.model_fingerprint, 'calibration': voucher.calibration,
            'reference': {'标准档': STANDARD_GEAR, '参照档窗口': f'{reference.gear_window[0]:.0f}–{reference.gear_window[1]:.0f}',
                          '参照单量': reference.count,
                          '参照中位': None if reference.center is None else round(reference.center, 4),
                          '参照上限': None if reference.fence is None else round(reference.fence, 4),
                          '参照指纹': reference.fingerprint, '参照可用': reference.usable},
            'totals': {'派单工位': voucher.occupied, '已释放': voucher.released, '仍占位': voucher.held,
                       '销单': settled, '占位': holding, '有效回执': voucher.effective_receipts,
                       '重复回执': voucher.duplicate_receipts, '被取代版次': voucher.superseded_receipts,
                       '回执隔离': len(voucher.issues)},
            'decisions': decision_rows(voucher),
            'issues': [issue.evidence() for issue in voucher.issues]}
