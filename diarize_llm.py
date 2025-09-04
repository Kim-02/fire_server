# diarize_llm.py
import os, json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM = """너는 119 신고 통화의 자막을 보고,
각 발화를 CALLER(신고자) 또는 OPERATOR(접수자)로 라벨링한다.
규칙:
- 질문/확인/안내는 OPERATOR
- 상황 설명/도움 요청은 CALLER
- 불확실하면 추정하되 짧은 단위로 나눔
JSON만 출력:
{
 "segments": [
   {"role": "CALLER"|"OPERATOR", "text": "문장", "start": null, "end": null}
 ]
}
"""

def split_by_speaker(transcript: str) -> dict:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content": SYSTEM},
            {"role":"user","content": transcript}
        ],
        temperature=0.2
    )
    raw = resp.choices[0].message.content.strip()
    try:
        data = json.loads(raw)
    except Exception:
        data = {"segments":[{"role":"CALLER","text":transcript,"start":None,"end":None}]}

    caller = " ".join(s.get("text","") for s in data.get("segments",[]) if s.get("role")=="CALLER")
    operator = " ".join(s.get("text","") for s in data.get("segments",[]) if s.get("role")=="OPERATOR")
    data["merged"] = {"caller": caller.strip(), "operator": operator.strip()}
    return data

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print('사용법: py diarize_llm.py "자막 텍스트"')
        raise SystemExit(1)
    out = split_by_speaker(sys.argv[1])
    print(json.dumps(out, ensure_ascii=False, indent=2))
