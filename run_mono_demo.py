# run_mono_demo.py
import os, json, time, uuid
from stt import transcribe
from diarize_llm import split_by_speaker
from extract import extract_keywords

def simple_predict(kw: dict) -> dict:
    level = 2
    score = 0.55
    if kw.get("urgency") == "HIGH":
        level, score = 4, 0.8
    if "연기" in (kw.get("hazards") or []):
        score += 0.05
    if (kw.get("floor") or 0) >= 3:
        score += 0.05
    score = round(min(score, 0.99), 2)
    likely = (
        (f'{kw["floor"]}층 ' if kw.get("floor") else "")
        + (kw.get("location_hint") or "")
    ).strip() or None
    return {
        "likely_location": likely,
        "cause": None,  # 필요시 규칙/모델로 채우기
        "risk_level": {"label": "높음" if level >= 4 else "보통", "level": level, "score": score},
        "confidence": score,
        "crew_recommendation": {
            "people": {"total": 12 if level >= 4 else 8, "breakdown": {"대원": 12 if level >= 4 else 8}},
            "vehicles": {"total": 4 if level >= 4 else 2, "breakdown": {"펌프": 2, "사다리": 1 if level >= 4 else 0, "구급": 1}},
            "equip": ["고압호스 100m × 2", "사다리(15m)", "열화상 카메라", "연기제거팬"],
        },
    }

def simple_search_similar(kw: dict) -> list[dict]:
    # 데모용 하드코딩(원하면 DB/FTS로 교체)
    cases = [
        {
            "id": "CASE-202307-0142",
            "summary": "아파트 2층 목재 가구 화재, 연기 다량, 인명대피 12명",
            "tags": {"incident_type": "화재", "hazards": ["연기"], "fuel": ["목재"], "floor": 2},
        },
        {
            "id": "CASE-202402-0310",
            "summary": "상가 3층 전기화재, 연기 중간, 대피 6명",
            "tags": {"incident_type": "화재", "hazards": ["연기"], "fuel": ["플라스틱"], "floor": 3},
        },
    ]
    def score(c):
        s = 0
        if c["tags"].get("incident_type") == kw.get("incident_type"): s += 0.3
        s += 0.2 * len(set(c["tags"].get("hazards", [])) & set(kw.get("hazards", [])))
        s += 0.2 * len(set(c["tags"].get("fuel", [])) & set(kw.get("fuel", [])))
        if c["tags"].get("floor") == kw.get("floor"): s += 0.1
        return round(s, 2)
    ranked = sorted(cases, key=score, reverse=True)
    return [{"id": c["id"], "summary": c["summary"], "match": score(c)} for c in ranked[:3]]

def build_screen_payload(transcript: str, diar: dict, kw: dict) -> dict:
    incident_id = str(int(time.time()))
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S+09:00", time.localtime())
    cur_date = time.strftime("%Y-%m-%d")
    cur_time = time.strftime("%H시 %M분 %S초")
    pred = simple_predict(kw)
    # 대화 turn 정리(시연: 시간은 비움)
    turns = [{"time": "", "role": s.get("role", ""), "text": s.get("text", "")} for s in diar.get("segments", [])]
    return {
        "incident_id": incident_id,
        "now": now_iso,
        "elapsed_since_fire": 0,
        "current_incident": {
            "date": cur_date,
            "time": cur_time,
            "address": kw.get("address") or "",   # 있으면 채우기
            "detail": kw.get("location_hint") or "",
            "type": "건물 화재" if kw.get("incident_type") == "화재" else (kw.get("incident_type") or None),
        },
        "ai_prediction": pred,
        "keywords": kw,
        "similar_cases": simple_search_similar(kw),
        "transcript_turns": turns,
    }

def run(audio_path: str, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)

    # 1) 음성 → 텍스트
    stt_res = transcribe(audio_path)
    transcript = stt_res["transcript"]
    with open(os.path.join(out_dir, "transcript.txt"), "w", encoding="utf-8") as f:
        f.write(transcript)

    # 2) 화자 분리
    diar = split_by_speaker(transcript)
    with open(os.path.join(out_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(diar, f, ensure_ascii=False, indent=2)

    # 3) 신고자 텍스트(없으면 전체) 추출
    caller_text = diar["merged"]["caller"] or transcript
    with open(os.path.join(out_dir, "caller.txt"), "w", encoding="utf-8") as f:
        f.write(caller_text)
    with open(os.path.join(out_dir, "operator.txt"), "w", encoding="utf-8") as f:
        f.write(diar["merged"]["operator"])

    # 4) 키워드
    kw = extract_keywords(caller_text)["keywords"]

    # 5) 화면 JSON 구성 및 저장
    payload = build_screen_payload(transcript, diar, kw)
    incident_json = os.path.join(out_dir, f"incident_{payload['incident_id']}.json")
    with open(incident_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("완료 ✅", os.path.abspath(out_dir))
    print("화면 JSON:", os.path.abspath(incident_json))

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("사용법: py run_mono_demo.py <오디오경로> <출력폴더>")
        raise SystemExit(1)
    run(sys.argv[1], sys.argv[2])
