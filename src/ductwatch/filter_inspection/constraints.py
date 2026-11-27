from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Callable

from .contracts import Job


@dataclass(frozen=True, slots=True)
class WorkOrder:
    job: Job
    assessment: Any

    def __post_init__(self):
        if self.job.key != self.assessment.raw.key:
            raise ValueError('处置工位与单据不匹配')


def apply_filter_inspection(fan_checks, admit: Callable, wait: Callable):
    resident_zones = Counter()
    for fan in fan_checks:
        pressure, setting, volume, dust, valve, age = fan.assessment.raw.input_values
        machine_room = fan.job.cohort
        spare = resident_zones[machine_room]
        if volume < 1200 and valve <= 14 and setting > 50:
            wait(fan, 'DAMPER_FEEDBACK_REQUIRED', '先查风阀反馈，之后标定滤网')
            continue
        if pressure >= 230 and spare >= 2:
            wait(fan, 'REFERENCE_MANOMETER_IN_USE', '同机房二级测压计已占用')
        elif admit(fan):
            resident_zones[machine_room] += int(pressure >= 180)
