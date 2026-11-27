from dataclasses import dataclass
from math import isfinite
from ..duct_checklists.contracts import DuctwatchRecord as RawObservation

RAW_KEYS = ('pressure_pa', 'fan_pct', 'flow_cmh', 'pm_index', 'open_pct', 'since_days')
FEATURE_KEYS = ('flow_resistance', 'fan_delivery', 'particle_load', 'return_factor', 'resistance_age')
FEATURE_NAMES = ('流量校正阻力', '转速归一风量', '积尘暴露', '回风供风比', '压差与使用期比例')


@dataclass(frozen=True, slots=True)
class FeatureState:
    fill: tuple[float, ...]
    offsets: tuple[float, ...]
    scales: tuple[float, ...]
    floor: tuple[float, ...]
    ceil: tuple[float, ...]
    fingerprint: str

    def __post_init__(self):
        if len(self.fill) != len(RAW_KEYS):
            raise ValueError('补值向量维数与字段表不匹配')
        if any(len(column) != len(FEATURE_KEYS) for column in (self.offsets, self.scales, self.floor, self.ceil)):
            raise ValueError('特征状态维数不匹配')
        if min(self.scales) <= 0:
            raise ValueError('特征尺度必须为正')


@dataclass(frozen=True, slots=True)
class FeatureVector:
    key: str
    cohort: str
    day: int
    values: tuple[float, ...]
    factors: tuple[float, ...]
    missing: tuple[str, ...]
    excursions: tuple[str, ...]
    outcome: float | None
    observed: bool
    input_values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class PreparedRuns:
    train: tuple[FeatureVector, ...]
    calibration: tuple[FeatureVector, ...]
    replay: tuple[FeatureVector, ...]
    live: tuple[FeatureVector, ...]

    def segments(self):
        return tuple((name, getattr(self, name)) for name in ('train', 'calibration', 'replay', 'live'))


@dataclass(frozen=True, slots=True)
class Proposal:
    name: str
    field: str
    before: float
    after: float
    work: int

    def __post_init__(self):
        if self.before == self.after or not isfinite(self.after) or self.work < 0:
            raise ValueError('推演动作需要实质变动和有效额度')

    def evidence(self):
        return {'情形': self.name, '变更项': self.field, '原值': self.before,
                '置换值': self.after, '用量': self.work}

@dataclass(frozen=True, slots=True)
class VentilationFactors:
    flow_per_setting: float
    load_per_open: float
    particulates_days: float
    scaled_pa: float
    restricted_air: float
    pressure_per_month: float
    nominal_shortfall: float
    fan_headroom: float

    def __post_init__(self):
        if not all(isfinite(amount) for amount in (self.flow_per_setting, self.load_per_open, self.particulates_days, self.scaled_pa, self.restricted_air, self.pressure_per_month, self.nominal_shortfall, self.fan_headroom)):
            raise ValueError('新风机组存在无效的作业量测')

    def explain(self, labels=None):
        return (
            ('每档供风量', round(self.flow_per_setting, 4)),
            ('按回风开度校正压差', round(self.load_per_open, 4)),
            ('积尘观察累积量', round(self.particulates_days, 4)),
            ('相对高压差读数', round(self.scaled_pa, 4)),
            ('按档位和开度推算制约', round(self.restricted_air, 4)),
            ('每月滤网压差', round(self.pressure_per_month, 4)),
            ('标称送风差额', round(self.nominal_shortfall, 4)),
            ('档位剩余', round(self.fan_headroom, 4)),
        )
