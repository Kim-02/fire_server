from dotenv import load_dotenv
load_dotenv()  # .env 의 OPENAI_API_KEY 로딩

import os
import time
import uuid
import json
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ===== 로컬 모듈 =====
from stt import transcribe
from extract import extract_keywords, extract_keywords_both
from run_mono_demo import run as pipeline_run
from mapper import to_fire_incident_nested

# ===== 기본 설정 =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def R(path: str) -> str:
    """BASE_DIR 기준 상대경로 → 절대경로"""
    return path if os.path.isabs(path) else os.path.join(BASE_DIR, path)


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY가 .env에 없습니다.")

os.makedirs(R("uploads"), exist_ok=True)
os.makedirs(R("results"), exist_ok=True)

app = FastAPI(title="Fire STT/Extract API", version="1.1.0")

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 필요 시 도메인 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 결과 JSON 정적 서빙 (브라우저에서 바로 GET 가능)
app.mount("/results", StaticFiles(directory=R("results")), name="results")

# ===== Pydantic 모델 =====
class ExtractIn(BaseModel):
    text: str
    mode: Optional[str] = "both"  # "facts" | "insights" | "both"

class TranscriptIn(BaseModel):
    text: str
    fire_data_pk: Optional[int] = None
    report_datetime: Optional[str] = None  # 없으면 서버 현재시각 사용(YYYY-MM-DD HH:MM:SS 권장)

# ===== 전사 → 표준 유틸 =====
def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_or_now(dt: Optional[str]) -> str:
    if not dt:
        return _now()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(dt, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
    return _now()


def _extract_floor(text: str) -> Optional[int]:
    m = re.search(r'(\d+)\s*층', text)
    return int(m.group(1)) if m else None


def _detect_ignition_material(text: str) -> Optional[str]:
    # 간단 키워드 기반 추정
    keywords = ["고무", "종이", "목재", "플라스틱", "천", "기름", "가스", "전기"]
    for k in keywords:
        if k in text:
            return k
    return None


def _guess_building_usage(text: str) -> Optional[str]:
    if "대학교" in text or "학교" in text:
        return "교육연구시설"
    if "아파트" in text or "주택" in text:
        return "공동주택"
    if "상가" in text or "가게" in text or "식당" in text:
        return "근린생활시설"
    return None


def _extract_location(text: str) -> Optional[str]:
    # 예: '한국기술교육대학교 담헌실학관'
    m = re.search(r'([가-힣A-Za-z0-9\s]*대학교\s*[가-힣A-Za-z0-9\s]*관)', text)
    if m:
        return m.group(1).strip()
    m = re.search(r'여기\s+([^\.\,]+?)입니다', text)
    return m.group(1).strip() if m else None


def transcript_to_standard(text: str,
                           fire_data_pk: Optional[int] = None,
                           report_dt: Optional[str] = None) -> Dict[str, Any]:
    floor = _extract_floor(text)
    usage = _guess_building_usage(text)
    ign_mat = _detect_ignition_material(text)
    loc = _extract_location(text)

    return {
        "fire_data_pk": fire_data_pk,
        "numeric": {
            "building_agreement_count": None,
            "total_floor_area": None,
            "soot_area": None,
            "floor_area": None,
            "ignition_floor": floor,
            "casualty_count": 0,           # 언급 없으면 0 가정
            "unit_temperature": None,
            "unit_humidity": None,
            "property_damage_amount": None,
            "total_floor_count": floor if floor else None,  # "6층 건물"일 때 총층수=6 추정
        },
        "info": {
            "building_structure": None,
            "building_usage_status": usage,
            "multi_use_flag": "N",
            "fuel_type": ign_mat,
            "ignition_device": None,
            "ignition_heat_source": None,
            "ignition_cause": None,
            "fire_management_target_flag": "N",
            "fire_station_name": None,
            "unit_wind_speed": None,
            "facility_location": loc,
            "combustion_expansion_material": None,
            "forest_fire_flag": "N",
            "report_datetime": _get_or_now(report_dt),
            "vehicle_fire_flag": "N",
            "initial_extinguish_datetime": None,
            "ignition_material": ign_mat,
            "special_fire_object_name": None,
            "wind_direction": None,
            "arrival_datetime": None,
            "fire_type": "건물 화재",
        }
    }


def _is_effectively_empty(std: Dict[str, Any]) -> bool:
    """numeric/info가 비었으면 빈 것으로 간주"""
    if not std:
        return True
    n = std.get("numeric")
    i = std.get("info")
    return (not n and not i) or (isinstance(n, dict) and not n and isinstance(i, dict) and not i)

# ===== 폴백 강화를 위한 깊은 탐색 유틸 =====
def _deep_find_text_candidates(obj: Any, max_len: int = 2000) -> List[str]:
    """
    dict/list 안을 전부 훑어 문장처럼 보이는 긴 문자열 후보를 모은다.
    """
    cand: List[str] = []

    def walk(x: Any):
        if isinstance(x, dict):
            for _, v in x.items():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str):
            s = x.strip()
            # 너무 짧은 값 제외, 영/한/숫자 등이 섞인 문장성 텍스트 우선
            if len(s) >= 10 and any(ch.isalpha() for ch in s):
                cand.append(s[:max_len])

    walk(obj)
    cand.sort(key=lambda s: len(s), reverse=True)  # 긴 텍스트 우선
    return cand


def _pick_transcript_like(candidates: List[str]) -> str:
    """
    후보들 중 '신고 대사/설명'처럼 보이는 문장을 우선 선택.
    """
    for s in candidates:
        if any(tok in s for tok in ["층", "불", "연기", "냄새", "대학교", "건물", "화재", "출동"]):
            return s
    return candidates[0] if candidates else ""

# ===== 엔드포인트 =====
@app.get("/health")
def health():
    return {"ok": True, "time": time.strftime("%Y-%m-%d %H:%M:%S")}


@app.post("/stt")
async def api_stt(file: UploadFile = File(...)):
    """
    오디오 업로드 → Whisper STT
    """
    suffix = os.path.splitext(file.filename or "")[1] or ".wav"
    temp_path = R(os.path.join("uploads", f"{uuid.uuid4().hex}{suffix}"))
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    try:
        res = transcribe(temp_path)  # { text: "...", ... } 형태 기대
        return {"ok": True, **res}
    except Exception as e:
        raise HTTPException(400, f"STT 실패: {e}")


@app.post("/extract")
def api_extract(body: ExtractIn):
    """
    텍스트 → 키워드 추출 (facts/insights/both)
    """
    try:
        mode = (body.mode or "both").lower()
        if mode == "facts":
            out = extract_keywords(body.text, strict=True)
        elif mode == "insights":
            out = extract_keywords(body.text, strict=False)
        else:
            out = extract_keywords_both(body.text)
        return {"ok": True, "result": out}
    except Exception as e:
        raise HTTPException(400, f"키워드 추출 실패: {e}")


@app.post("/normalize-nested")
def normalize_nested(raw: Dict[str, Any], save: bool = True):
    """
    원시 레코드(raw) → 표준 중첩 JSON 변환.
    기본은 results/normalize/<uuid>.json 로 저장 (save=false로 저장 off).
    """
    try:
        std = to_fire_incident_nested(raw).model_dump(exclude_none=True)

        if save:
            folder = R(os.path.join("results", "normalize"))
            os.makedirs(folder, exist_ok=True)
            fname = f"{uuid.uuid4().hex}.json"
            fpath = os.path.join(folder, fname)
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(std, f, ensure_ascii=False, indent=2)
            static_url = f"/results/normalize/{fname}"
            return {"ok": True, "data": std, "file_path": fpath, "file_url": static_url}

        return {"ok": True, "data": std}
    except Exception as e:
        raise HTTPException(400, f"정규화 실패: {e}")

@app.post("/pipeline")
async def pipeline(file: UploadFile, save: bool = True) -> Dict[str, Any]:
    """
    STT -> Extract -> Normalize 순으로 처리하는 pipeline
    """
    stt_result = await api_stt(file)
    transcript = stt_result["transcript"]

    extract_input = {"text": transcript, "mode": "both"}
    extract_result = api_extract(ExtractIn(**extract_input))

    raw = {
        "call_id": stt_result["call_id"],
        "lang": stt_result["lang"],
        "transcript": stt_result["transcript"],
        "extraction": extract_result["result"]
    }
    normalized = normalize_nested(raw, save=save)

    return raw

@app.post("/normalize-from-transcript")
def normalize_from_transcript(body: TranscriptIn):
    """
    통화 내역 텍스트만 받아서 → 표준 중첩 JSON(전 컬럼 포함) 생성.
    """
    std = transcript_to_standard(
        text=body.text,
        fire_data_pk=body.fire_data_pk,
        report_dt=body.report_datetime
    )
    return {"ok": True, "standard": std}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",          # 모듈명:인스턴스
        host="0.0.0.0",     # 모든 네트워크 인터페이스에서 접근 가능
        port=8000,
        reload=True         # 개발 편의용 자동 reload
    )