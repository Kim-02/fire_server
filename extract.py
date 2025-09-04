# extract.py
import os, json, time, re, argparse
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from openai import OpenAI

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
    fire_management_target_flag: Optional[str] = Field(None, description="방화관리대상 여부")
    unit_temperature: Optional[float] = Field(None, description="단위 기온")
    unit_humidity: Optional[float] = Field(None, description="단위 습도")
    unit_wind_speed: Optional[str] = Field(None, description="시간단위 풍속정보")
    facility_location: Optional[str] = Field(None, description="시설 장소")
    forest_fire_flag: Optional[bool] = Field(None, description="임야 발화 여부")
    total_floor_count: Optional[int] = Field(None, description="전체 층수")
    vehicle_fire_flag: Optional[bool] = Field(None, description="차량 화재 여부")
    ignition_material: Optional[str] = Field(None, description="착화물")
    special_fire_object_name: Optional[str] = Field(None, description="특정 소방대상물명")
    wind_direction: Optional[str] = Field(None, description="풍향 방위")

SYSTEM_PROMPT = """당신은 119 신고 대화에서 사건 속성을 추출하는 도메인 추출기입니다.
가능한 한 문맥과 상식으로 최대한 제가 주는 양식에 맞추어 추론해주세요.
해당 값에서 추론되는 키워드가 존재하지 않는다면, 굳이 추론할 필요 없습니다.
모르는 내용은 추론하지 말라는 뜻입니다. 할루시네이션을 일으키지 말아주세요.
'접수자(OPERATOR)의 질문'과 '신고자(CALLER)의 짧은 대답'도 단서입니다.
반드시 JSON만 출력하세요.



출력(JSON):
{
  "building_agreement_count": "int",        // 건물구조에 따른 동의 갯수
  "building_structure": "string[]",         // 건물 구조 (복수 값 가능)
  "building_usage_status": "string",        // 건물 사용 상태 (사용중/미사용/공사중 등)
  "total_floor_area": "float",              // 전체 바닥 면적 (㎡)
  "soot_area": "float",                     // 화재로 인한 그을음 면적 (㎡)
  "multi_use_flag": "bool",                 // 다중이용업 여부 (병원·백화점·지하상가 등)
  "fuel_type": "string",                    // 주요 연료/연소물
  "fire_management_target_flag": "string",  // 방화관리대상 여부
  "unit_temperature": "float",              // 단위 기온 (℃)
  "unit_humidity": "float",                 // 단위 습도 (%)
  "unit_wind_speed": "string",              // 단위 풍속 정보 (예: "3 m/s")
  "facility_location": "string",            // 시설 위치 (옥내/옥외/지하/옥상/주차장 등)
  "forest_fire_flag": "bool",               // 임야 발화 여부 (산불 여부)
  "total_floor_count": "int",               // 전체 층수
  "vehicle_fire_flag": "bool",              // 차량 화재 여부
  "ignition_material": "string",            // 착화물 (최초 발화 추정 물질)
  "special_fire_object_name": "string",     // 특정 소방대상물명 (변압기, 보일러, 가스탱크 등)
  "wind_direction": "string"                // 풍향 방위 (N, NE, E, SE, S, SW, W, NW) 풍향정보가 주어질 때만
}
"""

# ---------------------- 유틸 ----------------------
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
    # 디폴트 맵 (지침 양식 기반)
    return {
        "building_agreement_count": 0,
        "building_structure": [],
        "building_usage_status": None,
        "total_floor_area": 0.0,
        "soot_area": 0.0,
        "multi_use_flag": False,
        "fuel_type": None,
        "fire_management_target_flag": None,
        "unit_temperature": 0.0,
        "unit_humidity": 0.0,
        "unit_wind_speed": None,
        "facility_location": None,
        "forest_fire_flag": False,
        "total_floor_count": 0,
        "vehicle_fire_flag": False,
        "ignition_material": None,
        "special_fire_object_name": None,
        "wind_direction": None
    }

def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").lower())

def _filter_terms_by_literal(text: str, terms: List[str]) -> List[str]:
    nt = _norm(text)
    return [t for t in (terms or []) if _norm(t) in nt]

INCIDENT_LITERAL_MAP: Dict[str, List[str]] = {
    "화재": ["화재","불","불이","불났","불이났","불길","불났어요"],
    "구조": ["구조","갇혔","매몰","낭떠러지","붕괴로막혔","빠졌"],
    "구급": ["구급","심정지","호흡곤란","쓰러졌","의식없","출혈"],
}

def _incident_from_literal(text: str) -> Optional[str]:
    t = _norm(text)
    for key, kws in INCIDENT_LITERAL_MAP.items():
        for kw in kws:
            if _norm(kw) in t:
                return key
    return None

def _normalize_types(data: Dict[str, Any]) -> Dict[str, Any]:
    base = {
        "building_agreement_count": 0,
        "building_structure": [],
        "building_usage_status": None,
        "total_floor_area": 0.0,
        "soot_area": 0.0,
        "multi_use_flag": False,
        "fuel_type": None,
        "fire_management_target_flag": None,
        "unit_temperature": 0.0,
        "unit_humidity": 0.0,
        "unit_wind_speed": None,
        "facility_location": None,
        "forest_fire_flag": False,
        "total_floor_count": 0,
        "vehicle_fire_flag": False,
        "ignition_material": None,
        "special_fire_object_name": None,
        "wind_direction": None
    }
    base.update(data or {})

    # 리스트 강제 변환
    if not isinstance(base["building_structure"], list):
        base["building_structure"] = [str(base["building_structure"])] if base["building_structure"] else []

    # int 변환
    for key in ["building_agreement_count", "total_floor_count"]:
        try:
            if base[key] is not None:
                base[key] = int(base[key])
        except Exception:
            base[key] = 0

    # float 변환
    for key in ["total_floor_area", "soot_area", "unit_temperature", "unit_humidity"]:
        try:
            if base[key] is not None:
                base[key] = float(base[key])
        except Exception:
            base[key] = 0.0

    # bool 변환
    for key in ["multi_use_flag", "forest_fire_flag", "vehicle_fire_flag"]:
        v = base.get(key)
        if isinstance(v, str):
            base[key] = v.lower() in ["true", "1", "yes", "y"]
        else:
            base[key] = bool(v)

    # 문자열 보정
    for key in ["building_usage_status", "fuel_type", "fire_management_target_flag",
                "unit_wind_speed", "facility_location", "ignition_material",
                "special_fire_object_name", "wind_direction"]:
        v = base.get(key)
        base[key] = str(v) if v not in [None, ""] else None

    return base

# ---------------------- 규칙 선추출 & 병합 ----------------------
DIR_WORDS = {
    "북": "N", "북쪽": "N", "북서": "NW", "북서풍": "NW", "북동": "NE", "북동풍": "NE",
    "남": "S", "남쪽": "S", "남서": "SW", "남서풍": "SW", "남동": "SE", "남동풍": "SE",
    "동": "E", "동쪽": "E", "서": "W", "서쪽": "W"
}

SPECIAL_OBJECTS = [
    "변압기", "변전실", "전기실", "배전반", "보일러", "보일러실", "가스탱크", "LPG", "LPG 탱크",
    "유류탱크", "화학물질", "약품창고", "페인트", "용접기", "배터리실", "UPS", "태양광 인버터"
]

FUEL_WORDS = ["목재", "플라스틱", "종이", "석유", "배터리", "가스", "식용유", "폐기물", "고무", "비닐", "의류", "가구"]

STRUCTURE_WORDS = ["공장", "창고", "상가", "주택", "아파트", "기숙사", "학교", "병원", "사무실", "지하주차장", "주차장", "지하", "옥상"]

def _match_any(text: str, words):
    return [w for w in words if w in text]

def _parse_number(pattern: str, text: str, cast=float):
    m = re.search(pattern, text)
    if not m:
        return None
    try:
        return cast(m.group(1).replace(",", ""))
    except:
        return None

def prefill_from_rules(text: str) -> Dict[str, Any]:
    t = (text or "").strip()

    out: Dict[str, Any] = {
        "building_agreement_count": 0,           # 세대/동의 수 같은 값이 명시되면 추출 (기본 0)
        "building_structure": [],                # ["공장","창고"...] 등 다중 가능
        "building_usage_status": None,           # 사용중/공가/공사중 등
        "total_floor_area": 0.0,                 # "연면적 1200㎡" 등에서 추출
        "soot_area": 0.0,                        # 면적으로 특정되면 반영
        "multi_use_flag": False,                 # 다중이용시설(병원·백화점·대형점 등) 키워드 시 True
        "fuel_type": None,                       # 주요 연료/연소물 단일 대표
        "fire_management_target_flag": None,     # (지정여부 불명확 → 규정상 판단 어렵다면 None 유지)
        "unit_temperature": 0.0,                 # “온도 35도/35℃”
        "unit_humidity": 0.0,                    # “습도 60%”
        "unit_wind_speed": None,                 # “풍속 3m/s”
        "facility_location": None,               # “옥내/옥외/지하/옥상/주차장 …”
        "forest_fire_flag": False,               # 산림/산불/임야 키워드
        "total_floor_count": 0,                  # “6층 건물”
        "vehicle_fire_flag": False,              # 차량 화재 여부
        "ignition_material": None,               # 최초 착화 추정물(텍스트에서 우선 후보)
        "special_fire_object_name": None,        # 변압기/보일러/가스탱크 등
        "wind_direction": None                   # N/NE/... (DIR_WORDS 맵)
    }

    # 1) 구조/시설 위치 추정
    structures = _match_any(t, STRUCTURE_WORDS)
    if structures:
        out["building_structure"] = list(dict.fromkeys(structures))  # 중복 제거&원순서 유지

    # 시설 위치 힌트
    if "옥외" in t or "실외" in t: out["facility_location"] = "옥외"
    if "옥내" in t or "실내" in t: out["facility_location"] = "옥내"
    if "지하" in t: out["facility_location"] = "지하"
    if "옥상" in t: out["facility_location"] = "옥상"
    if "주차장" in t: out["facility_location"] = "주차장"

    # 다중이용시설 추정
    if any(k in t for k in ["병원", "백화점", "대형마트", "지하상가", "역사", "지하도상가", "학원", "영화관", "유흥주점"]):
        out["multi_use_flag"] = True

    # 2) 층수/연면적 등 수치 추출
    # "6층 건물" → total_floor_count
    m = re.search(r"(\d+)\s*층\s*건물|(\d+)\s*층\b", t)
    if m:
        num = next(g for g in m.groups() if g)
        try:
            out["total_floor_count"] = int(num)
        except:
            pass

    # 연면적: "연면적 1200", "연면적 1,200㎡", "연면적 1,200m2"
    area = _parse_number(r"연면적\s*([0-9,]+(?:\.\d+)?)\s*(?:㎡|m2|m²)?", t, float)
    if area is not None:
        out["total_floor_area"] = float(area)

    # 그을음 면적(있다면): "그을음 50㎡"
    soot = _parse_number(r"(?:그을음|그을림)\s*([0-9,]+(?:\.\d+)?)\s*(?:㎡|m2|m²)", t, float)
    if soot is not None:
        out["soot_area"] = float(soot)

    # 3) 연료/착화물
    fuels = _match_any(t, FUEL_WORDS)
    if fuels:
        # 대표 fuel_type은 가장 먼저 매칭된 항목으로
        out["fuel_type"] = fuels[0]
        # ignition_material은 보다 구체적인 단서가 있으면 그걸로, 없으면 fuel_type 재사용
        # 예: “고무 타는 냄새” → 고무
        if "타는 냄새" in t:
            # 냄새와 같이 언급된 단어 우선
            cand = _match_any(t, fuels)
            out["ignition_material"] = cand[0] if cand else fuels[0]
        else:
            out["ignition_material"] = fuels[0]

    # 4) 차량/산림 여부
    if any(k in t for k in ["차량", "자동차", "트럭", "버스", "오토바이", "승용차", "화물차"]):
        out["vehicle_fire_flag"] = True
        # 차량만 언급되고 건물 언급이 전혀 없으면 위치를 옥외로 힌트
        if not out["building_structure"]:
            out["facility_location"] = out["facility_location"] or "옥외"

    if any(k in t for k in ["산불", "산림", "임야", "수풀", "야산"]):
        out["forest_fire_flag"] = True
        if not out["facility_location"]:
            out["facility_location"] = "옥외"

    # 5) 특수화재물(특정 위험 설비) 키워드
    specials = _match_any(t, SPECIAL_OBJECTS)
    if specials:
        out["special_fire_object_name"] = specials[0]

    # 6) 사용 상태 추정
    if any(k in t for k in ["사용 중", "영업 중", "운영 중", "수업 중", "근무 중"]):
        out["building_usage_status"] = "사용중"
    elif any(k in t for k in ["미사용", "공가", "빈집", "공실"]):
        out["building_usage_status"] = "미사용"
    elif any(k in t for k in ["공사 중", "리모델링 중"]):
        out["building_usage_status"] = "공사중"

    # 7) 기상 값 추출 (온도/습도/풍속/풍향)
    temp = _parse_number(r"(?:온도|기온|온도는)\s*([0-9]+(?:\.\d+)?)\s*(?:도|℃)", t, float)
    if temp is not None:
        out["unit_temperature"] = float(temp)

    hum = _parse_number(r"(?:습도|습도는)\s*([0-9]+(?:\.\d+)?)\s*%", t, float)
    if hum is not None:
        out["unit_humidity"] = float(hum)

    ws = _parse_number(r"(?:풍속|바람)\s*([0-9]+(?:\.\d+)?)\s*m/?s", t, float)
    if ws is not None:
        out["unit_wind_speed"] = f"{ws} m/s"

    for k, v in DIR_WORDS.items():
        if k in t:
            out["wind_direction"] = v
            break

    # 8) 세대/동의 수(있을 때): "세대 120세대", "동의 30"
    agree = _parse_number(r"(?:세대|동의)\s*([0-9,]+)", t, int)
    if agree is not None:
        out["building_agreement_count"] = int(agree)

    # 9) “연기/하얀 연기” 같은 신고 단서 → 직접 필드가 없으므로 참고만
    #    (필요 시 soot_area, fuel_type 추정을 강화하는 규칙을 여기 확장)

    return out

def merge_rule_and_model(rule: Dict[str, Any], model: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(model or {})

    rule = rule or {}
    # 리스트 병합 대상 필드
    list_merge_keys = {"building_structure"}

    for k, v in rule.items():
        if k in list_merge_keys:
            # 리스트 합집합(중복 제거 + 원순서 보존)
            prev_list = merged.get(k) or []
            new_list = v or []
            if not isinstance(prev_list, list):
                prev_list = [prev_list] if prev_list else []
            if not isinstance(new_list, list):
                new_list = [new_list] if new_list else []
            merged[k] = list(dict.fromkeys(prev_list + new_list))
        else:
            # rule 값이 실값이면 덮어쓰기, 아니면 기존 유지
            merged[k] = v if v not in [None, [], "", {}] else merged.get(k)

    # 타입 및 기본값 정규화
    return _normalize_types(merged)

# ---------------------- 핵심: 한 번 추출 ----------------------
def _extract_once(transcript: str, strict: bool) -> Dict[str, Any]:
    t0 = time.time()

    # 규칙 선추출
    rule_prefill = prefill_from_rules(transcript)

    # 모델 추출
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript}
        ]
    )
    raw = (resp.choices[0].message.content or "").strip()
    model_json = _normalize_types(_safe_json_extract(raw))

    # 병합
    merged = merge_rule_and_model(rule_prefill, model_json)

    # 엄격 모드(발화 기반 사실만 남김)
    if strict:
        merged["hazards"] = _filter_terms_by_literal(transcript, merged.get("hazards") or [])
        merged["fuel"]    = _filter_terms_by_literal(transcript, merged.get("fuel") or [])
        merged["incident_type"] = _incident_from_literal(transcript)  # 직언 없으면 None
        if merged.get("structure_type") not in ["공장","창고","상가","차량","야외","산림","공동주택"]:
            merged["structure_type"] = None
        else:
            if _norm(merged["structure_type"]) not in _norm(transcript):
                merged["structure_type"] = None

    validated = KeywordsV1(**_normalize_types(merged))
    ms = int((time.time() - t0) * 1000)
    return {"keywords": validated.model_dump(), "model": f"gpt-4o-mini({'strict' if strict else 'hybrid'})", "latency_ms": ms}

# ---------------------- 공개 API ----------------------
def extract_keywords(transcript: str, strict: bool = False) -> Dict[str, Any]:
    return _extract_once(transcript, strict)

def extract_keywords_both(transcript: str) -> Dict[str, Any]:
    """facts(발화 기반) + insights(추론 허용) 둘 다 반환"""
    facts    = _extract_once(transcript, strict=True)
    insights = _extract_once(transcript, strict=False)
    return {"facts": facts, "insights": insights}

# ---------------------- CLI ----------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="119 신고 키워드 추출")
    parser.add_argument("text", help="텍스트 한 덩어리 (또는 PowerShell: (Get-Content file.txt -Raw))")
    parser.add_argument("--mode", choices=["facts","insights","both"], default="both",
                        help="facts=발화기반(strict), insights=추론허용(hybrid), both=둘다")
    args = parser.parse_args()

    if args.mode == "facts":
        out = extract_keywords(args.text, strict=True)
    elif args.mode == "insights":
        out = extract_keywords(args.text, strict=False)
    else:
        out = extract_keywords_both(args.text)

    print(json.dumps(out, ensure_ascii=False, indent=2))
