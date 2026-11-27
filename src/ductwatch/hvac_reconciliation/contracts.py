from dataclasses import dataclass

from ..duct_checklists.contracts import Issue

POLICY_VERSION = 'ductwatch.20261125.v1'


@dataclass(frozen=True, slots=True)
class LedgerCheck:
    raw: int
    isolated: int
    mature_excluded: int
    scored: int
    capacity: int
    resource_used: int
    balance: int
    states: tuple[tuple[str, int], ...]

    def __post_init__(self):
        if self.capacity != self.resource_used + self.balance:
            raise ArithmeticError('不能出具额度不平的凭证')
        if self.scored != sum(number for _, number in self.states):
            raise ArithmeticError('不能出具单据数量不平的凭证')


@dataclass(frozen=True, slots=True)
class BatchReceipt:
    stamp: str
    batch_hash: str
    policy_hash: str
    totals: LedgerCheck
    decisions: tuple[tuple[str, str, int, str, float], ...]


@dataclass(frozen=True, slots=True)
class ReceiptTicket:
    """换网实测回执：fingerprint 只含单号、工日、版次与量测，重跑回执身份不变。"""
    key: str
    day: int
    received: int
    revision: int
    position: int
    values: tuple[float | None, ...]
    missing: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ReferenceBand:
    """派单时冻结的历史正常实绩参照，晚到的记录不补入。"""
    gear_window: tuple[float, float]
    count: int
    center: float | None
    fence: float | None
    fingerprint: str
    usable: bool

    def __post_init__(self):
        if self.count < 0:
            raise ArithmeticError('参照单量不能为负')
        if self.usable and (self.fence is None or self.center is None):
            raise ArithmeticError('可用参照缺少上限')
        if self.fence is not None and self.center is not None and self.fence < self.center:
            raise ArithmeticError('参照上限低于参照中位')


@dataclass(frozen=True, slots=True)
class SettlementDecision:
    key: str
    cohort: str
    cost: int
    decision: str
    reason: str
    summary: str
    dispatch_estimate: float
    receipt_score: float | None
    receipt_estimate: float | None
    receipt_day: int | None
    receipt_revision: int | None
    receipt_fingerprint: str | None

    def __post_init__(self):
        if self.decision not in ('销单', '占位'):
            raise ValueError('核销决定只能是销单或占位')
        if self.cost < 1:
            raise ValueError('核销工位应为正')


@dataclass(frozen=True, slots=True)
class SettlementVoucher:
    """核销凭证：可回查实测指纹与参照指纹，工位释放守恒。"""
    stamp: str
    dispatch_stamp: str
    feature_stamp: str
    model: str
    model_fingerprint: str
    calibration: str
    reference: ReferenceBand
    decisions: tuple[SettlementDecision, ...]
    issues: tuple[Issue, ...]
    occupied: int
    released: int
    held: int
    effective_receipts: int
    duplicate_receipts: int
    superseded_receipts: int

    def __post_init__(self):
        if min(self.occupied, self.released, self.held) < 0:
            raise ArithmeticError('核销凭证工位不能为负')
        if self.released + self.held != self.occupied:
            raise ArithmeticError('核销凭证的工位不守恒')
        keys = [item.key for item in self.decisions]
        if len(set(keys)) != len(keys):
            raise ArithmeticError('核销凭证的单号不唯一')
        settled = sum(item.cost for item in self.decisions if item.decision == '销单')
        holding = sum(item.cost for item in self.decisions if item.decision == '占位')
        if settled != self.released or holding != self.held:
            raise ArithmeticError('核销凭证的工位汇总不符')
        if min(self.effective_receipts, self.duplicate_receipts, self.superseded_receipts) < 0:
            raise ArithmeticError('回执统计不能为负')
