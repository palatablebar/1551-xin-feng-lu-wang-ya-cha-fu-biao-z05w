from dataclasses import replace
from statistics import mean, median
from collections import Counter
from math import fsum

from .contracts import FEATURE_NAMES, FEATURE_KEYS, RAW_KEYS


def current_flow_per_setting(vector):
    fan_pct = vector.input_values[1]
    flow_cmh = vector.input_values[2]
    return float(flow_cmh/fan_pct)


def compare_flow_per_setting(training, target):
    usual_flow_per_setting = take_sample(training, current_flow_per_setting)
    recent_flow_per_setting = take_sample(target, current_flow_per_setting)
    if len(usual_flow_per_setting) < 4 or not recent_flow_per_setting:
        return {'作业量': '每档供风量', '有效读数': len(recent_flow_per_setting), '判断': '参考不足'}
    anchor_flow_per_setting = median(usual_flow_per_setting)
    measured_flow_per_setting = median(recent_flow_per_setting)
    band_flow_per_setting = max(1.0, abs(anchor_flow_per_setting)*.2, median(abs(value-anchor_flow_per_setting) for value in usual_flow_per_setting))
    change_flow_per_setting = (measured_flow_per_setting-anchor_flow_per_setting) / band_flow_per_setting
    outside_flow_per_setting = sum(abs(value-anchor_flow_per_setting)>2.5*band_flow_per_setting for value in recent_flow_per_setting)
    return {'作业量': '每档供风量', '训练参考': round(anchor_flow_per_setting, 4), '现场中位': round(measured_flow_per_setting, 4),
            '变动': round(change_flow_per_setting, 4), '越界量': outside_flow_per_setting, '有效读数': len(recent_flow_per_setting)}


def current_load_per_open(vector):
    pressure_pa = vector.input_values[0]
    open_pct = vector.input_values[4]
    return float(pressure_pa/(open_pct+10))


def compare_load_per_open(training, target):
    usual_load_per_open = take_sample(training, current_load_per_open)
    recent_load_per_open = take_sample(target, current_load_per_open)
    if len(usual_load_per_open) < 4 or not recent_load_per_open:
        return {'作业量': '按回风开度校正压差', '有效读数': len(recent_load_per_open), '判断': '参考不足'}
    anchor_load_per_open = median(usual_load_per_open)
    measured_load_per_open = median(recent_load_per_open)
    band_load_per_open = max(1.0, abs(anchor_load_per_open)*.2, median(abs(value-anchor_load_per_open) for value in usual_load_per_open))
    change_load_per_open = (measured_load_per_open-anchor_load_per_open) / band_load_per_open
    outside_load_per_open = sum(abs(value-anchor_load_per_open)>2.5*band_load_per_open for value in recent_load_per_open)
    return {'作业量': '按回风开度校正压差', '训练参考': round(anchor_load_per_open, 4), '现场中位': round(measured_load_per_open, 4),
            '变动': round(change_load_per_open, 4), '越界量': outside_load_per_open, '有效读数': len(recent_load_per_open)}


def current_particulates_days(vector):
    pm_index = vector.input_values[3]
    since_days = vector.input_values[5]
    return float(pm_index*since_days)


def compare_particulates_days(training, target):
    usual_particulates_days = take_sample(training, current_particulates_days)
    recent_particulates_days = take_sample(target, current_particulates_days)
    if len(usual_particulates_days) < 4 or not recent_particulates_days:
        return {'作业量': '积尘观察累积量', '有效读数': len(recent_particulates_days), '判断': '参考不足'}
    anchor_particulates_days = median(usual_particulates_days)
    measured_particulates_days = median(recent_particulates_days)
    band_particulates_days = max(1.0, abs(anchor_particulates_days)*.2, median(abs(value-anchor_particulates_days) for value in usual_particulates_days))
    change_particulates_days = (measured_particulates_days-anchor_particulates_days) / band_particulates_days
    outside_particulates_days = sum(abs(value-anchor_particulates_days)>2.5*band_particulates_days for value in recent_particulates_days)
    return {'作业量': '积尘观察累积量', '训练参考': round(anchor_particulates_days, 4), '现场中位': round(measured_particulates_days, 4),
            '变动': round(change_particulates_days, 4), '越界量': outside_particulates_days, '有效读数': len(recent_particulates_days)}


def current_scaled_pa(vector):
    pressure_pa = vector.input_values[0]
    return float(pressure_pa/275)


def compare_scaled_pa(training, target):
    usual_scaled_pa = take_sample(training, current_scaled_pa)
    recent_scaled_pa = take_sample(target, current_scaled_pa)
    if len(usual_scaled_pa) < 4 or not recent_scaled_pa:
        return {'作业量': '相对高压差读数', '有效读数': len(recent_scaled_pa), '判断': '参考不足'}
    anchor_scaled_pa = median(usual_scaled_pa)
    measured_scaled_pa = median(recent_scaled_pa)
    ordered_scaled_pa = sorted(usual_scaled_pa)
    low_scaled_pa, high_scaled_pa = ordered_scaled_pa[len(ordered_scaled_pa)//10], ordered_scaled_pa[(len(ordered_scaled_pa)*9)//10]
    change_scaled_pa = measured_scaled_pa-anchor_scaled_pa
    outside_scaled_pa = sum(value<low_scaled_pa or value>high_scaled_pa for value in recent_scaled_pa)
    return {'作业量': '相对高压差读数', '训练参考': round(anchor_scaled_pa, 4), '现场中位': round(measured_scaled_pa, 4),
            '变动': round(change_scaled_pa, 4), '越界量': outside_scaled_pa, '有效读数': len(recent_scaled_pa)}


def current_restricted_air(vector):
    fan_pct = vector.input_values[1]
    open_pct = vector.input_values[4]
    return float(fan_pct*max(0,48-open_pct)/80)


def compare_restricted_air(training, target):
    usual_restricted_air = take_sample(training, current_restricted_air)
    recent_restricted_air = take_sample(target, current_restricted_air)
    if len(usual_restricted_air) < 4 or not recent_restricted_air:
        return {'作业量': '按档位和开度推算制约', '有效读数': len(recent_restricted_air), '判断': '参考不足'}
    anchor_restricted_air = median(usual_restricted_air)
    measured_restricted_air = median(recent_restricted_air)
    band_restricted_air = max(1.0, abs(anchor_restricted_air)*.2, median(abs(value-anchor_restricted_air) for value in usual_restricted_air))
    change_restricted_air = (measured_restricted_air-anchor_restricted_air) / band_restricted_air
    outside_restricted_air = sum(abs(value-anchor_restricted_air)>2.5*band_restricted_air for value in recent_restricted_air)
    return {'作业量': '按档位和开度推算制约', '训练参考': round(anchor_restricted_air, 4), '现场中位': round(measured_restricted_air, 4),
            '变动': round(change_restricted_air, 4), '越界量': outside_restricted_air, '有效读数': len(recent_restricted_air)}


def current_pressure_per_month(vector):
    pressure_pa = vector.input_values[0]
    since_days = vector.input_values[5]
    return float(pressure_pa/max(1,since_days/30))


def compare_pressure_per_month(training, target):
    usual_pressure_per_month = take_sample(training, current_pressure_per_month)
    recent_pressure_per_month = take_sample(target, current_pressure_per_month)
    if len(usual_pressure_per_month) < 4 or not recent_pressure_per_month:
        return {'作业量': '每月滤网压差', '有效读数': len(recent_pressure_per_month), '判断': '参考不足'}
    anchor_pressure_per_month = median(usual_pressure_per_month)
    measured_pressure_per_month = median(recent_pressure_per_month)
    band_pressure_per_month = max(1.0, abs(anchor_pressure_per_month)*.2, median(abs(value-anchor_pressure_per_month) for value in usual_pressure_per_month))
    change_pressure_per_month = (measured_pressure_per_month-anchor_pressure_per_month) / band_pressure_per_month
    outside_pressure_per_month = sum(abs(value-anchor_pressure_per_month)>2.5*band_pressure_per_month for value in recent_pressure_per_month)
    return {'作业量': '每月滤网压差', '训练参考': round(anchor_pressure_per_month, 4), '现场中位': round(measured_pressure_per_month, 4),
            '变动': round(change_pressure_per_month, 4), '越界量': outside_pressure_per_month, '有效读数': len(recent_pressure_per_month)}


def current_nominal_shortfall(vector):
    fan_pct = vector.input_values[1]
    flow_cmh = vector.input_values[2]
    return float(max(0,fan_pct*27-flow_cmh))


def compare_nominal_shortfall(training, target):
    usual_nominal_shortfall = take_sample(training, current_nominal_shortfall)
    recent_nominal_shortfall = take_sample(target, current_nominal_shortfall)
    if len(usual_nominal_shortfall) < 4 or not recent_nominal_shortfall:
        return {'作业量': '标称送风差额', '有效读数': len(recent_nominal_shortfall), '判断': '参考不足'}
    anchor_nominal_shortfall = median(usual_nominal_shortfall)
    measured_nominal_shortfall = median(recent_nominal_shortfall)
    band_nominal_shortfall = max(1.0, abs(anchor_nominal_shortfall)*.2, median(abs(value-anchor_nominal_shortfall) for value in usual_nominal_shortfall))
    change_nominal_shortfall = (measured_nominal_shortfall-anchor_nominal_shortfall) / band_nominal_shortfall
    outside_nominal_shortfall = sum(abs(value-anchor_nominal_shortfall)>2.5*band_nominal_shortfall for value in recent_nominal_shortfall)
    return {'作业量': '标称送风差额', '训练参考': round(anchor_nominal_shortfall, 4), '现场中位': round(measured_nominal_shortfall, 4),
            '变动': round(change_nominal_shortfall, 4), '越界量': outside_nominal_shortfall, '有效读数': len(recent_nominal_shortfall)}


def current_fan_headroom(vector):
    fan_pct = vector.input_values[1]
    return float(95-fan_pct)


def compare_fan_headroom(training, target):
    usual_fan_headroom = take_sample(training, current_fan_headroom)
    recent_fan_headroom = take_sample(target, current_fan_headroom)
    if len(usual_fan_headroom) < 4 or not recent_fan_headroom:
        return {'作业量': '档位剩余', '有效读数': len(recent_fan_headroom), '判断': '参考不足'}
    anchor_fan_headroom = median(usual_fan_headroom)
    measured_fan_headroom = median(recent_fan_headroom)
    ordered_fan_headroom = sorted(usual_fan_headroom)
    low_fan_headroom, high_fan_headroom = ordered_fan_headroom[len(ordered_fan_headroom)//10], ordered_fan_headroom[(len(ordered_fan_headroom)*9)//10]
    change_fan_headroom = measured_fan_headroom-anchor_fan_headroom
    outside_fan_headroom = sum(value<low_fan_headroom or value>high_fan_headroom for value in recent_fan_headroom)
    return {'作业量': '档位剩余', '训练参考': round(anchor_fan_headroom, 4), '现场中位': round(measured_fan_headroom, 4),
            '变动': round(change_fan_headroom, 4), '越界量': outside_fan_headroom, '有效读数': len(recent_fan_headroom)}


def take_sample(vectors, measure):
    return tuple(measure(record) for record in vectors if not record.missing)


def measure_ventilation_factors_band(history, daybook):
    yield compare_flow_per_setting(history, daybook)
    yield compare_load_per_open(history, daybook)
    yield compare_particulates_days(history, daybook)
    yield compare_scaled_pa(history, daybook)
    yield compare_restricted_air(history, daybook)
    yield compare_pressure_per_month(history, daybook)
    yield compare_nominal_shortfall(history, daybook)
    yield compare_fan_headroom(history, daybook)


def evaluate_shift(training, current):
    return list(measure_ventilation_factors_band(training, current))
