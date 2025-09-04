# extractKeys.py
import re
from collections import OrderedDict
from typing import List, Dict, Any

# 규칙 세트
RULES_STRUCTURE_SIMPLE = [
    (r"비닐하우스\s*파이프조", "비닐하우스파이프조"),
    (r"비닐하우스", "비닐하우스"),
    (r"컨테이너조\s*컨테이너|컨테이너조|컨테이너", "컨테이너조"),
    (r"샌드위치패널조", "샌드위치패널조"),
    (r"철골조", "철골조"),
    (r"철근콘크리트조", "철근콘크리트조"),
    (r"SRC|철골철근콘크리트조", "SRC"),
    (r"벽돌조", "벽돌조"),
    (r"블록조", "블록조"),
    (r"목조", "목조"),
    (r"슬라브가", "슬라브"),
    (r"스레트가", "슬레이트"),
    (r"시멘트기와", "시멘트기와"),
    (r"한식기와|와가", "기와"),
    (r"칼라피복철판", "칼라피복철판"),
]

# 건물 사용 상태
RULES_USAGE_STATUS = [
    (r"개축", "개축"),
    (r"공가", "공가"),
    (r"신축", "신축"),
    (r"증축", "증축"),
    (r"철거", "철거중"),
    (r"공사\s*중|리모델링", "기타 공사중"),
    (r"사용\s*중|영업\s*중|운영\s*중|수업\s*중|근무\s*중", "사용중"),
]
RULES_MULTI_USE = [
    r"노래방", r"피시방", r"PC방", r"영화관", r"마트", r"백화점", r"학원",
    r"클럽", r"주점", r"지하상가", r"역사", r"놀이공원", r"병원"
]
RULES_FUEL_TYPE = [
    (r"경유", "유류 경유"),
    (r"등유", "유류 등유"),
    (r"중유", "유류 중유"),
    (r"가솔린", "유류 가솔린"),
    (r"알코올", "유류 알코올"),
    (r"LNG|액화천연가스", "가스 액화천연가스(LNG)"),
    (r"LPG|액화석유가스", "가스 액화석유가스(LPG)"),
    (r"부탄", "가스 부탄가스"),
    (r"가스", "가스 기타 가연성가스"),
    (r"나무", "고체연료 나무"),
    (r"목탄", "고체연료 목탄"),
    (r"석탄", "고체연료 석탄"),
    (r"종이", "고체연료 종이"),
    (r"화학", "고체연료 화학연료"),
    (r"고체", "고체연료 기타 고체연료"),
    (r"110V", "전기 110V이하 상용전원"),
    (r"12V", "전기 직류 12V 이하(배터리) 전원"),
    (r"24V", "전기 직류 24V 이상(배터리) 전원"),
    (r"22\.9 ?kv", "전기 22.9kv 이상 전원"),
    (r"3300V", "전기 3,300V이상 상용전원"),
    (r"380/220V", "전기 380/220V이상 상용전원"),
    (r"440V", "전기 440V이상 상용전원"),
    (r"전기", "전기 기타 전원"),
    (r"유류", "유류 기타 액체연료"),
    (r"기타", "기타 기타"),
]
RULES_FIRE_MANAGEMENT = [
    r"방화관리", r"소방대상", r"소방관리", r"특정소방대상", r"방화 대상"
]
RULES_WIND_SPEED = [
    (r"매우\s*강|태풍|돌풍|강풍", "매우 강한 바람"),
    (r"강한\s*바람|세찬 바람", "강한 바람"),
    (r"보통\s*바람|평범한 바람", "보통 바람"),
    (r"약한\s*바람|산들바람", "약한 바람"),
    (r"잔잔|고요|무풍", "잔잔함"),
]
RULES_FACILITY_LOCATION = [
    # 임야/숲/들불
    (r"임야|숲|산불|들불|들판|묘지|목초지|논밭|공유림|국유림|사유림|군사격장", "임야"),
    # 주거
    (r"주택|단독주택|공동주택|아파트|연립주택|다세대|다가구|상가주택|기숙사|주상복합", "주거"),
    # 도로
    (r"도로|전봇대|가로등", "도로"),
    # 야외/공터
    (r"공터|야외|야적장|모닥불|볏짚|쓰레기", "야외"),
    # 선박/항공기
    (r"선박|어선|항공기|비행기|헬리콥터|유람선|화물선|여객선|바지선", "선박/항공기"),
    # 판매·업무·공공기관
    (r"상가|백화점|시장|마트|할인점|쇼핑센터|오피스텔|빌딩|회사|신문사|금융기관|공관|청사", "판매/업무"),
    (r"군사시설|막사", "군사시설"),
    (r"교도소|구치소|교정시설", "교정시설"),
    # 숙박
    (r"모텔|호텔|여관|여인숙|펜션|민박|콘도|숙박공유업|산장", "숙박"),
    # 의료·복지
    (r"병원|의원|한의원|치과|종합병원|요양병원|장례식장|정신병원", "의료시설"),
    (r"약국", "의료시설"),
    (r"경로당|양로원|어린이집|유치원|노인복지시설|사회복지시설|아동복지시설|장애인재활시설", "노유자시설"),
    (r"요양소|요양시설", "노유자시설"),
    (r"마사지|목욕장|사우나|찜질방|요가수련장|단식수련원", "건강시설"),
    # 청소년시설
    (r"청소년수련원|청소년야영장|청소년수련관|청소년문화의집", "청소년시설"),
    # 자동차/철도/건설·농업 기계
    (r"자동차|승용차|트럭|버스|화물차|오토바이|승합차|캠핑용|특수자동차", "자동차"),
    (r"철도차량|기관차|전동차", "철도차량"),
    (r"건설기계|덤프트럭|굴삭기", "건설기계"),
    (r"농업기계|경운기|트랙터", "농업기계"),
    # 위험물·가스제조소
    (r"위험물제조소|가스제조소", "위험물/가스제조소"),
]
RULES_FOREST_FIRE = [
    (r"산정상|정상", "산정상"),
    (r"산중턱|중턱", "산중턱"),
    (r"산아래|산기슭|산밑", "산아래"),
    (r"평지", "평지"),
    (r"사유림", "사유림"),
    (r"국유림", "국유림"),
    (r"공유림", "공유림"),
    (r"숲", "숲"),
    (r"들판|들불", "들판"),
    (r"논밭|논밭두렁", "논밭두렁"),
    (r"묘지", "묘지"),
    (r"기타", "기타"),
]
RULES_VEHICLE_FIRE = [
    (r"고속도로", "고속도로"),
    (r"일반도로", "일반도로"),
    (r"도로", "도로"),
    (r"터널", "터널"),
    (r"주차장", "주차장"),
    (r"철도차량", "철도차량"),
    (r"객실|좌석", "객실"),
    (r"바퀴", "바퀴"),
    (r"공지", "공지"),
    (r"미상", "미상"),
]
RULES_IGNITION = [
    # 가구류
    (r"소파", "가구 소파"),
    (r"옷장|책장", "가구 옷장,책장"),
    (r"침대|매트리스", "가구 침대,매트리스"),
    (r"테이블|의자", "가구 테이블,의자"),
    (r"가구", "가구 기타"),

    # 식품류
    (r"튀김유", "식품 튀김유"),
    (r"음식|음식물", "식품 음식물"),
    (r"식품", "식품 기타"),

    # 전기·전자류
    (r"기판", "전기,전자 기판"),
    (r"절연유", "전기,전자 절연유"),
    (r"케이스", "전기,전자 케이스"),
    (r"배선", "전기,전자 내부배선"),
    (r"콘센트|스위치", "전기,전자 콘센트,스위치"),
    (r"전선", "전기,전자 전선피복"),
    (r"모터|히터|램프", "전기,전자 작동장치"),
    (r"전자기기", "전기,전자 기타"),

    # 종이·목재·건초류
    (r"풀|나뭇잎", "종이,목재,건초등 풀,나뭇잎"),
    (r"건초", "종이,목재,건초등 건초"),
    (r"나무", "종이,목재,건초등 나무"),
    (r"잔디", "종이,목재,건초등 잔디"),
    (r"종이", "종이,목재,건초등 종이"),
    (r"톱밥", "종이,목재,건초등 톱밥"),
    (r"목재|합판", "종이,목재,건초등 목재,합판"),

    # 침구·직물류
    (r"의류", "침구,직물류 의류"),
    (r"카펫", "침구,직물류 카펫"),
    (r"커튼", "침구,직물류 커튼"),
    (r"걸레|행주", "침구,직물류 행주,기름걸레"),
    (r"이불|베개|시트", "침구,직물류 이불"),
    (r"부직포", "침구,직물류 부직포"),
    (r"침구|직물", "침구,직물류 기타"),

    # 간판·차양막류
    (r"광고판", "간판,차양막등 광고판"),
    (r"차양막", "간판,차양막등 차양막"),
    (r"네온사인", "간판,차양막등 네온사인"),
    (r"플래카드", "간판,차양막등 플래카드"),
    (r"간판", "간판,차양막등 기타"),

    # 자동차·철도차량·선박·항공기
    (r"배관", "자동차,철도차량,선박,항공기 배관"),
    (r"범퍼", "자동차,철도차량,선박,항공기 범퍼"),

    # 미상/기타
    (r"미상", "미상"),
    (r"기타", "기타"),
]
RULES_SPECIAL_OBJECTS = [
    (r"공장", "공장"),
    (r"묘지", "묘지 관련 시설"),
    (r"문화재", "문화재"),
    (r"지하가", "지하가"),
    (r"지하구", "지하구"),
    (r"공동주택", "공동주택"),
    (r"교정시설", "교정시설"),
    (r"발전", "발전시설"),
    (r"숙박", "숙박시설"),
    (r"업무", "업무시설"),
    (r"운동", "운동시설"),
    (r"운수", "운수시설"),
    (r"위락", "위락시설"),
    (r"의료", "의료시설"),
    (r"장례", "장례시설"),
    (r"종교", "종교시설"),
    (r"창고", "창고시설"),
    (r"문화집회|운동시설", "문화집회 및 운동시설"),
    (r"판매|영업", "판매시설 및 영업시설"),
    (r"노유자", "노유자시설"),
    (r"복합건축물", "복합건축물"),
    (r"청소년", "청소년시설"),
    (r"위험물", "위험물저장 및 처리시설"),
    (r"관광|휴게", "관광휴게시설"),
    (r"교육|연구", "교육연구시설"),
    (r"근린생활", "근린생활시설"),
    (r"통신|촬영", "통신촬영시설"),
    (r"동식물", "동식물관련시설"),
    (r"위생", "위생등관련시설"),
    (r"자동차", "운수자동차관련시설"),
]
RULES_WIND = [
    (r"(북동\s*풍|북동쪽\s*바람)", "NE"),
    (r"(북서\s*풍|북서쪽\s*바람)", "NW"),
    (r"(남동\s*풍|남동쪽\s*바람)", "SE"),
    (r"(남서\s*풍|남서쪽\s*바람)", "SW"),
    (r"(북\s*풍|북쪽\s*바람)", "N"),
    (r"(남\s*풍|남쪽\s*바람)", "S"),
    (r"(동\s*풍|동쪽\s*바람)", "E"),
    (r"(서\s*풍|서쪽\s*바람)", "W"),
]
#helper

def _norm(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\u3000", " ")
    s = re.sub(r"\s+", " ", s.strip())
    return s

#extracter
def extract_special_fire_object(text: str) -> str:
    for pattern, label in RULES_SPECIAL_OBJECTS:
        if re.search(pattern, text):
            return label
    return ""

def extract_ignition_material(text: str) -> str:
    found = []
    for pattern, label in RULES_IGNITION:
        if re.search(pattern, text):
            found.append(label)
    return " ".join(dict.fromkeys(found)) if found else ""

def extract_forest_fire(text: str) -> List[str]:
    found = []
    for pattern, label in RULES_FOREST_FIRE:
        if re.search(pattern, text):
            found.append(label)
    return list(dict.fromkeys(found))  # 중복 제거 & 순서 보존

def extract_building_structure(text: str) -> List[str]:
    found = []
    for pattern, label in RULES_STRUCTURE_SIMPLE:
        if re.search(pattern, text):
            found.append(label)
    return list(dict.fromkeys(found))  # 중복 제거 & 순서 보존

def extract_building_usage_status(text: str) -> str:
    for pattern, label in RULES_USAGE_STATUS:
        if re.search(pattern, text):
            return label
    return ""

def extract_multi_use_flag(text: str) -> str:
    for kw in RULES_MULTI_USE:
        if re.search(kw, text):
            return "Y"
    return "N"

def extract_vehicle_fire(text: str) -> List[str]:
    found = []
    for pattern, label in RULES_VEHICLE_FIRE:
        if re.search(pattern, text):
            found.append(label)
    return list(dict.fromkeys(found))  # 중복 제거 & 순서 보존

def extract_fuel_type(text: str) -> str:
    found = []
    for pattern, label in RULES_FUEL_TYPE:
        if re.search(pattern, text, re.IGNORECASE):
            found.append(label)
    found = list(dict.fromkeys(found))  # 중복 제거, 순서 유지
    return " ".join(found) if found else ""

def extract_fire_management_flag(text: str) -> str:
    for kw in RULES_FIRE_MANAGEMENT:
        if re.search(kw, text):
            return "Y"
    return "N"
def extract_unit_wind_speed(text: str) -> str:
    for pattern, label in RULES_WIND_SPEED:
        if re.search(pattern, text):
            return label
    return ""  # 기본값
def extract_facility_location(text: str) -> List[str]:
    found = []
    for pattern, label in RULES_FACILITY_LOCATION:
        if re.search(pattern, text):
            found.append(label)
    return list(dict.fromkeys(found))  # 중복 제거 & 순서 보존

def extract_wind_direction(text: str) -> str:
    for pattern, label in RULES_WIND:
        if re.search(pattern, text):
            return label
    return ""


def prefill(transcript: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    text = transcript or ""
    bs = extract_building_structure(text)
    if bs:
        out["building_structure"] = bs

    bu = extract_building_usage_status(text)
    if bu:
        out["building_usage_status"] = bu

    mu = extract_multi_use_flag(text)
    if mu == "Y":
        out["multi_use_flag"] = mu

    ft = extract_fuel_type(text)
    if ft:
        out["fuel_type"] = ft

    # 방화관리대상 여부
    fm = extract_fire_management_flag(text)
    out["fire_management_target_flag"] = fm

    # 풍속
    uw = extract_unit_wind_speed(text)
    out["unit_wind_speed"] = uw

    # 시설 위치
    fl = extract_facility_location(text)
    if fl:
        out["facility_location"] = fl

    # 산불 여부
    ff = extract_forest_fire(text)
    if ff:
        out["forest_fire_flag"] = ff

    #차량
    vf = extract_vehicle_fire(text)
    if vf:
        out["vehicle_fire_flag"] = vf

    #착화물
    im = extract_ignition_material(text)
    if im:
        out["ignition_material"] = im

    # special_fire_object_name
    so = extract_special_fire_object(text)
    if so:
        out["special_fire_object_name"] = so

    # wind_direction
    wd = extract_wind_direction(text)
    if wd:
        out["wind_direction"] = wd

    return out
