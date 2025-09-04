# extract.py
import os, json, time, re, argparse
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from openai import OpenAI

import extractKeys as keys

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------- 스키마 ----------------------
class People(BaseModel):
    num_involved: Optional[int] = None
    num_trapped: Optional[int] = None

class KeywordsV1(BaseModel):
    building_agreement_count: Optional[int] = Field(None, description="건물구조에 따른 동의 갯수")
    building_structure: Optional[List[str]] = Field(None, description="건물구조 (복수 값 가능)")
    building_usage_status: Optional[str] = Field(None, description="건물 사용 상태")
    total_floor_area: Optional[float] = Field(None, description="전체 바닥 면적")
    soot_area: Optional[float] = Field(None, description="화재로 인한 그을음 면적")
    multi_use_flag: Optional[bool] = Field(None, description="다중이용업 여부")
    fuel_type: Optional[str] = Field(None, description="동력원 연료명")
    fire_management_target_flag: Optional[bool] = Field(None, description="방화관리대상 여부")
    unit_temperature: Optional[float] = Field(None, description="단위 기온")
    unit_humidity: Optional[float] = Field(None, description="단위 습도")
    unit_wind_speed: Optional[str] = Field(None, description="시간단위 풍속정보")
    facility_location: Optional[List[str]] = Field(None, description="시설 장소")
    forest_fire_flag: Optional[List[str]] = Field(None, description="임야 발화")
    total_floor_count: Optional[int] = Field(None, description="전체 층수")
    vehicle_fire_flag: Optional[List[str]] = Field(None, description="차량 화재 여부")
    ignition_material: Optional[str] = Field(None, description="착화물")
    special_fire_object_name: Optional[str] = Field(None, description="특정 소방대상물명")
    wind_direction: Optional[str] = Field(None, description="풍향 방위")

SYSTEM_PROMPT = """당신은 119 신고 대화에서 사건 속성을 추출하는 도메인 추출기입니다.
가능한 한 문맥과 상식으로 제가 주는 양식에 맞추어 추론해주세요.
해당 값에서 추론되는 키워드가 존재하지 않는다면, 굳이 추론할 필요 없습니다.
모르는 내용은 추론하지 말라는 뜻입니다. 할루시네이션을 일으키지 말아주세요.
'접수자(OPERATOR)의 질문'과 '신고자(CALLER)의 짧은 대답'도 단서입니다.
반드시 JSON만 출력하세요.
만약 출력 데이터가 없다면 공백으로 출력하세요
추가 지시사항 (숫자/단위 처리):
- 모든 수치값은 원문에 등장하면 반드시 지정된 타입으로 변환하세요.
- "total_floor_count"는 int로만 추출 (예: "10층 건물" → 10).
- "building_agreement_count"도 int로만 추출 (예: "120세대" → 120).
- "unit_temperature"는 float (예: "35도" → 35.0).
- "unit_humidity"는 float (예: "60%" → 60.0).

출력(JSON):
{
  "building_agreement_count": "int",
  "building_structure": "string[]",
  "building_usage_status": "string",
  "total_floor_area": "float",
  "soot_area": "float",
  "multi_use_flag": "bool",
  "fuel_type": "string",
  "fire_management_target_flag": "bool",
  "unit_temperature": "float",
  "unit_humidity": "float",
  "unit_wind_speed": "string",
  "facility_location": "string[]",
  "forest_fire_flag": "string[]",
  "total_floor_count": "int",
  "vehicle_fire_flag": "string[]",
  "ignition_material": "string",
  "special_fire_object_name": "string",
  "wind_direction": "string"
}
"""

# ---------------------- 유틸 ----------------------
BASE: Dict[str, Any] = {
    "building_agreement_count": 0,
    "building_structure": [],
    "building_usage_status": None,
    "total_floor_area": 0.0,
    "soot_area": 0.0,
    "multi_use_flag": False,
    "fuel_type": None,
    "fire_management_target_flag": False,
    "unit_temperature": 0.0,
    "unit_humidity": 0.0,
    "unit_wind_speed": None,
    "facility_location": [],
    "forest_fire_flag": [],
    "total_floor_count": 0,
    "vehicle_fire_flag": [],
    "ignition_material": None,
    "special_fire_object_name": None,
    "wind_direction": None
}

LIST_FIELDS = {"building_structure", "facility_location", "forest_fire_flag", "vehicle_fire_flag"}
INT_FIELDS  = {"building_agreement_count", "total_floor_count"}
FLT_FIELDS  = {"total_floor_area", "soot_area", "unit_temperature", "unit_humidity"}
BOOL_FIELDS = {"multi_use_flag", "fire_management_target_flag"}

def _safe_json_extract(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e != -1 and e > s:
        try:
            return json.loads(text[s:e+1])
        except Exception:
            pass
    m = re.search(r"\{(?:[^{}]|(?R))*\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {}

def _normalize_types(d: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(BASE)
    out.update(d or {})

    for k in LIST_FIELDS:
        v = out.get(k)
        if v is None: out[k] = []
        elif not isinstance(v, list): out[k] = [v]

    for k in INT_FIELDS:
        try: out[k] = int(out.get(k) or 0)
        except: out[k] = 0

    for k in FLT_FIELDS:
        try: out[k] = float(out.get(k) or 0.0)
        except: out[k] = 0.0

    for k in BOOL_FIELDS:
        v = out.get(k)
        if isinstance(v, str):
            out[k] = v.strip().lower() in {"1","y","yes","true","t"}
        else:
            out[k] = bool(v)

    for k, v in list(out.items()):
        if k not in LIST_FIELDS and k not in INT_FIELDS and k not in FLT_FIELDS and k not in BOOL_FIELDS:
            if v == "": out[k] = None
    return out

def _filter_terms_by_literal(text: str, terms: List[str]) -> List[str]:
    nt = re.sub(r"\s+", "", (text or "").lower())
    return [t for t in (terms or []) if re.sub(r"\s+", "", t.lower()) in nt]

INCIDENT_LITERAL_MAP: Dict[str, List[str]] = {
    "화재": ["화재","불","불이","불났","불이났","불길","불났어요"],
    "구조": ["구조","갇혔","매몰","낭떠러지","붕괴로막혔","빠졌"],
    "구급": ["구급","심정지","호흡곤란","쓰러졌","의식없","출혈"],
}

def _incident_from_literal(text: str) -> Optional[str]:
    t = re.sub(r"\s+", "", (text or "").lower())
    for key, kws in INCIDENT_LITERAL_MAP.items():
        for kw in kws:
            if re.sub(r"\s+", "", kw.lower()) in t:
                return key
    return None

# ---------------------- 규칙/모델 병합 ----------------------
def merge_rule_and_model(rule: Dict[str, Any], model: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(BASE)

    # 모델 먼저
    merged.update(model or {})

    # 리스트 필드 합집합
    for k in LIST_FIELDS:
        rl = rule.get(k) or []
        ml = merged.get(k) or []
        if not isinstance(rl, list): rl = [rl]
        if not isinstance(ml, list): ml = [ml] if ml else []
        seen, out = set(), []
        for v in ml + rl:
            if v is None: continue
            if v not in seen:
                seen.add(v); out.append(v)
        merged[k] = out

    # 나머지 필드: 규칙 값이 실값이면 덮어씀
    for k, v in (rule or {}).items():
        if k in LIST_FIELDS:
            continue
        if v not in [None, "", [], {}]:
            merged[k] = v

    return _normalize_types(merged)

# ---------------------- 핵심 추출 ----------------------
def _call_openai(transcript: str) -> Dict[str, Any]:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript}
        ]
    )
    raw = (resp.choices[0].message.content or "").strip()
    return _safe_json_extract(raw)

def _extract_once(transcript: str, strict: bool) -> Dict[str, Any]:
    t0 = time.time()

    # 규칙: building_structure 우선 추출
    rule_prefill = keys.prefill(transcript)

    # 모델 JSON
    model_json = _normalize_types(_call_openai(transcript))

    # 병합
    merged = merge_rule_and_model(rule_prefill, model_json)

    # strict 모드 후처리(그대로 유지)
    if strict:
        merged["hazards"] = _filter_terms_by_literal(transcript, merged.get("hazards") or [])
        merged["fuel"]    = _filter_terms_by_literal(transcript, merged.get("fuel") or [])
        merged["incident_type"] = _incident_from_literal(transcript)
        if merged.get("structure_type") not in ["공장","창고","상가","차량","야외","산림","공동주택"]:
            merged["structure_type"] = None
        else:
            if (merged["structure_type"] or "").replace(" ", "").lower() not in (transcript or "").replace(" ", "").lower():
                merged["structure_type"] = None

    validated = KeywordsV1(**_normalize_types(merged))
    ms = int((time.time() - t0) * 1000)
    return {"keywords": validated.model_dump(), "model": f"gpt-4o-mini({'strict' if strict else 'hybrid'})", "latency_ms": ms}

# ---------------------- 공개 API ----------------------
def extract_keywords(transcript: str, strict: bool = False) -> Dict[str, Any]:
    return _extract_once(transcript, strict)

def extract_keywords_both(transcript: str) -> Dict[str, Any]:
    facts    = _extract_once(transcript, strict=True)
    insights = _extract_once(transcript, strict=False)
    return {"facts": facts, "insights": insights}

# ---------------------- TEST ----------------------
txt = "여기 강남구 역삼동 오피스텔 12층 건물인데요,지금 6층에서 불이 나서 연기가 심하게 나고 있어요.안에 직원들이 아직 몇 명 있는 것 같아요. 불은 전기 배선 타는 냄새가 납니다."
print("=== INPUT ===")
print(txt)
out = extract_keywords(txt, strict=False)  # 인사이트 병합
print("=== OUTPUT ===")
print(json.dumps(out, ensure_ascii=False, indent=2))
print("→ building_structure:", out["keywords"].get("building_structure"))