# stt.py
import os, sys, subprocess, shlex, time, uuid
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def convert_to_wav16k(src_path: str) -> str:
    """모든 오디오를 Whisper 친화적 wav(16kHz, mono, PCM)로 변환"""
    dst_path = f"{os.path.splitext(src_path)[0]}_fixed.wav"
    cmd = f'ffmpeg -y -i "{src_path}" -ar 16000 -ac 1 -acodec pcm_s16le "{dst_path}"'
    subprocess.run(shlex.split(cmd), check=True)
    return dst_path

def transcribe(audio_path: str):
    fixed = convert_to_wav16k(audio_path)
    with open(fixed, "rb") as f:
        tr = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe", 
            file=f
        )
    return {
        "call_id": str(uuid.uuid4()),
        "transcript": tr.text,
        "lang": "ko"
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: py stt.py <오디오경로>")
        sys.exit(1)
    res = transcribe(sys.argv[1])
    print(res)
