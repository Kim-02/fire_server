# mapper.py
from typing import Any, Dict, Optional, Iterable
from datetime import datetime
from models import FireIncidentNested, NumericBlock, InfoBlock

def _join_nonempty(parts: Iterable[Optional[str]], sep: str=" / ") -> Optional[str]:
    vals = [str(p).strip() for p in parts if p not in (None, "", "null", "NULL")]
    return sep.join(vals) if vals else None

def _to_int(val: Any) -> Optional[int]:
    try:
        if val is None or str(val).strip() == "":
            return None
        s = "".join(ch for ch in str(val) if ch.isdigit() or ch == "-")
        return int(s) if s else None
    except:
        return None

def _to_float(val: Any) -> Optional[float]:
    try:
        if val is None or str(val).strip() == "":
            return None
        return float(str(val).replace(",", ""))
    except:
        return None

def _sum_int(*vals: Any) -> Optional[int]:
    nums = [_to_int(v) or 0 for v in vals if v is not None]
    if not nums:
        return None
    return sum(nums)

def _yn(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip().upper()
    if s in ("Y","YES","T","TRUE","1"):
        return "Y"
    if s in ("N","NO","F","FALSE","0"):
        return "N"
    return None

def _dt(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    for fmt in ("%Y%m%d%H%M%S","%Y-%m-%d %H:%M:%S","%Y/%m/%d %H:%M:%S",
                "%Y-%m-%d","%Y/%m/%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            continue
    return None

def _flag_from_keywords(*vals: Optional[str], keywords=("임야","산불","임야화재","산림")) -> Optional[str]:
    text = " ".join([v for v in vals if v]).lower()
    if not text:
        return None
    return "Y" if any(k.lower() in text for k in keywords) else "N"

def _vehicle_flag(*vals: Optional[str]) -> Optional[str]:
    text = " ".join([v for v in vals if v]).lower()
    if not text:
        return None
    keys = ("차량","자동차","승용","트럭","버스","화물","car","vehicle")
    return "Y" if any(k in text for k in keys) else "N"

def to_fire_incident_nested(raw: Dict[str, Any]) -> FireIncidentNested:
    numeric = NumericBlock(
        building_agreement_count=_to_int(raw.get("bldg_rscu_dngct")),
        total_floor_area=_to_float(raw.get("bldg_gfa")),
        soot_area=_to_float(raw.get("so_area")),
        floor_area=_to_float(raw.get("bttm_area")),
        ignition_floor=_to_int(raw.get("igtn_flr_nm")),
        casualty_count=_sum_int(raw.get("injpsn_cnt"), raw.get("dth_cnt")),
        unit_temperature=_to_float(raw.get("hr_unit_artmp")),
        unit_humidity=_to_float(raw.get("hr_unit_hum")),
        property_damage_amount=_to_float(raw.get("prpt_dam_amt")),
        total_floor_count=_sum_int(raw.get("grnd_nofl"), raw.get("udgd_nofl")),
    )

    info = InfoBlock(
        building_structure=_join_nonempty([
            raw.get("bldg_srtfrm_nm"),
            raw.get("bldg_strctr_nm"),
            raw.get("bldg_srtrf_nm"),
        ]),
        building_usage_status=raw.get("bldg_stts_nm"),
        multi_use_flag=_yn(raw.get("mub_yn")),
        fuel_type=_join_nonempty([raw.get("smtpr_lclsf_nm"), raw.get("smtpr_sclsf_nm")]),
        ignition_device=_join_nonempty([raw.get("igtn_istr_lclsf_nm"), raw.get("igtn_istr_sclsf_nm")]),
        ignition_heat_source=_join_nonempty([raw.get("igtn_htsrc_nm"), raw.get("igtn_htsrc_sclsf_nm")]),
        ignition_cause=_join_nonempty([raw.get("igtn_dmnt_lclsf_nm"), raw.get("igtn_dmnt_sclsf_nm")]),
        fire_management_target_flag=_yn(raw.get("arson_mng_trgt_yn")),
        fire_station_name=_join_nonempty([raw.get("cntr_nm"), raw.get("frstn_nm")]),
        unit_wind_speed=raw.get("hr_unit_wspd_info"),
        facility_location=_join_nonempty([
            raw.get("fclt_plc_lclsf_nm"),
            raw.get("fclt_plc_sclsf_nm"),
            raw.get("fclt_plc_mclsf_nm"),
        ]),
        combustion_expansion_material=_join_nonempty([
            raw.get("cmbs_expobj_lclsf_nm"),
            raw.get("cmbs_expobj_sclsf_nm"),
        ]),
        forest_fire_flag=_flag_from_keywords(raw.get("fnd_igtn_pstn_nm"), raw.get("fnd_fire_se_nm")),
        report_datetime=_dt(raw.get("rcpt_dt")),
        vehicle_fire_flag=_vehicle_flag(raw.get("vhcl_igtn_pstn_nm"), raw.get("vhcl_plc_nm")),
        initial_extinguish_datetime=_dt(raw.get("bgnn_potfr_dt")),
        ignition_material=_join_nonempty([raw.get("frst_igobj_lclsf_nm"), raw.get("frst_igobj_sclsf_nm")]),
        special_fire_object_name=raw.get("spfptg_nm"),
        wind_direction=raw.get("wndrct_brng"),
        arrival_datetime=_dt(raw.get("grnds_arvl_dt")),
        fire_type=raw.get("fire_type_nm"),
    )

    return FireIncidentNested(
        fire_data_pk=_to_int(raw.get("fire_data_pk")),
        numeric=numeric,
        info=info,
    )
