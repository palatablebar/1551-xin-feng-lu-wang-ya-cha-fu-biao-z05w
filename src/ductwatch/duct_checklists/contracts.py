from dataclasses import dataclass

FIELDS = {'pressure_pa': ('滤网压差', 'Pa', 14, 340),
 'fan_pct': ('风机档位', '%', 18, 95),
 'flow_cmh': ('供风量', 'm³/h', 180, 3600),
 'pm_index': ('外部颗粒计数', '个/L', 3, 250),
 'open_pct': ('回风阀开度', '%', 5, 95),
 'since_days': ('换网后使用', '天', 3, 185)}
LIMITS = {'result_max': 1}


class MeasureIssue(ValueError):
    def __init__(self, field: str, code: str):
        super().__init__(f'{field}:{code}')
        self.field = field
        self.code = code


@dataclass(frozen=True, slots=True)
class DuctwatchRecord:
    key: str
    cohort: str
    day: int
    received: int
    revision: int
    result_day: int | None
    outcome: float | None
    observed: bool
    pressure_pa: float | None
    fan_pct: float | None
    flow_cmh: float | None
    pm_index: float | None
    open_pct: float | None
    since_days: float | None

    def signature(self):
        return (self.key, self.cohort, self.day, self.revision, self.result_day, self.outcome, self.observed,
                *(getattr(self, key) for key in FIELDS))


@dataclass(frozen=True, slots=True)
class Issue:
    source_row: int
    key: str
    field: str
    code: str

    def evidence(self):
        return {'行号': self.source_row, '单号': self.key, '字段': FIELDS.get(self.field, (self.field,))[0],
                '原因': self.code}


@dataclass(frozen=True, slots=True)
class DecodeResult:
    entries: tuple[DuctwatchRecord, ...]
    issues: tuple[Issue, ...]
    source_rows: int
