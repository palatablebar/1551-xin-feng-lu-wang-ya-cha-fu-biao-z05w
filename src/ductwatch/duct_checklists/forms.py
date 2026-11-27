from collections.abc import Mapping
from decimal import Decimal

from .contracts import MeasureIssue


from dataclasses import dataclass


def form_number(form, sheet, name, minimum, maximum):
    from .service import number

    table = form.get(sheet)
    if not isinstance(table, Mapping):
        raise MeasureIssue(sheet, 'FORM_SECTION_REQUIRED')
    return Decimal(str(number(table.get(name), name, minimum, maximum)))


@dataclass(frozen=True, slots=True)
class DuctChecklistsSheet:
    delta_millipascal: Decimal
    fan_basis_points: Decimal
    supply_m3h: Decimal
    outside_particle_litre: Decimal
    return_basis_points: Decimal
    filter_running_hours: Decimal

    def fields(self):
        return {
            'pressure_pa': float(self.delta_millipascal) / 1000,
            'fan_pct': float(self.fan_basis_points) / 100,
            'flow_cmh': float(self.supply_m3h),
            'pm_index': float(self.outside_particle_litre),
            'open_pct': float(self.return_basis_points) / 100,
            'since_days': float(self.filter_running_hours) / 24,
        }

    def validation(self):
        fields = self.fields()
        pressure_pa = fields['pressure_pa']
        fan_pct = fields['fan_pct']
        flow_cmh = fields['flow_cmh']
        pm_index = fields['pm_index']
        open_pct = fields['open_pct']
        since_days = fields['since_days']
        flow_per_setting = flow_cmh/fan_pct
        supplied_air = flow_cmh*open_pct/100
        filter_work_days = since_days*max(1,pm_index/100)
        pressure_fan_load = pressure_pa/(1+fan_pct/30)
        alerts = []
        if flow_per_setting>165:
            alerts.append(('supply_m3h', 'SUPPLY_SETTING_INCONSISTENT'))
        if supplied_air<30 and pressure_fan_load>170:
            alerts.append(('return_basis_points', 'DAMPER_FEEDBACK_UNRELIABLE'))
        if filter_work_days>400 and pressure_pa>290:
            alerts.append(('filter_running_hours', 'FILTER_WITNESS_REQUIRED'))
        return tuple(alerts)


def read_duct_checklists(form):
    return DuctChecklistsSheet(
        delta_millipascal=form_number(form, '机组本体', 'delta_millipascal', 14000, 340000),
        fan_basis_points=form_number(form, '机组本体', 'fan_basis_points', 1800, 9500),
        supply_m3h=form_number(form, '回风抄读', 'supply_m3h', 180, 3600),
        outside_particle_litre=form_number(form, '回风抄读', 'outside_particle_litre', 3, 250),
        return_basis_points=form_number(form, '滤网登记', 'return_basis_points', 500, 9500),
        filter_running_hours=form_number(form, '滤网登记', 'filter_running_hours', 72, 4440),
    )


def explicit_rows(form):
    if not isinstance(form, Mapping):
        raise MeasureIssue('form', 'FORM_OBJECT_REQUIRED')
    note = read_duct_checklists(form)
    return note.fields(), note.validation()


def check_native_history(source):
    if not isinstance(source, Mapping) or 'form' not in source:
        return source
    if any(key in source for key in ('pressure_pa', 'fan_pct', 'flow_cmh', 'pm_index', 'open_pct', 'since_days')):
        raise MeasureIssue('form','MIXED_FORM_AND_FLAT_READING')
    converted, flags = explicit_rows(source['form'])
    if flags:
        raise MeasureIssue(*flags[0])
    return {**source, **converted}
