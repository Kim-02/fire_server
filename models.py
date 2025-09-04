# models.py
from typing import Optional
from pydantic import BaseModel, Field

class NumericBlock(BaseModel):
    building_agreement_count: Optional[int] = None
    total_floor_area: Optional[float] = None
    soot_area: Optional[float] = None
    floor_area: Optional[float] = None
    ignition_floor: Optional[int] = None
    casualty_count: Optional[int] = None
    unit_temperature: Optional[float] = None
    unit_humidity: Optional[float] = None
    property_damage_amount: Optional[float] = None
    total_floor_count: Optional[int] = None

class InfoBlock(BaseModel):
    building_structure: Optional[str] = None
    building_usage_status: Optional[str] = None
    multi_use_flag: Optional[str] = Field(None, pattern="^(Y|N)$")
    fuel_type: Optional[str] = None
    ignition_device: Optional[str] = None
    ignition_heat_source: Optional[str] = None
    ignition_cause: Optional[str] = None
    fire_management_target_flag: Optional[str] = Field(None, pattern="^(Y|N)$")
    fire_station_name: Optional[str] = None
    unit_wind_speed: Optional[str] = None
    facility_location: Optional[str] = None
    combustion_expansion_material: Optional[str] = None
    forest_fire_flag: Optional[str] = Field(None, pattern="^(Y|N)$")
    report_datetime: Optional[str] = None              # YYYY-MM-DD HH:MM:SS
    vehicle_fire_flag: Optional[str] = Field(None, pattern="^(Y|N)$")
    initial_extinguish_datetime: Optional[str] = None  # YYYY-MM-DD HH:MM:SS
    ignition_material: Optional[str] = None
    special_fire_object_name: Optional[str] = None
    wind_direction: Optional[str] = None
    arrival_datetime: Optional[str] = None             # YYYY-MM-DD HH:MM:SS
    fire_type: Optional[str] = None

class FireIncidentNested(BaseModel):
    fire_data_pk: Optional[int] = None
    numeric: NumericBlock
    info: InfoBlock
