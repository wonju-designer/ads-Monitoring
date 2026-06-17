"""
Gemini API 분석기
수집된 광고 데이터를 Gemini로 분석하여 인사이트를 생성합니다.
"""
import json
import urllib.request
import urllib.parse
from dataclasses import dataclass
from typing import Any
from config import GEMINI_API_KEY, GEMINI_MODEL, BRANDS
from collectors import MetaAd, GoogleAd, HomepageEvent


@dataclass
class BrandInsight:
    brand_id: str
    brand_name: str
    meta_summary: str
    google_summary: str
    homepage_summary: str
    key_message: str        # 이번 주 핵심 메시지/톤
    notable_point: str      # 아이즈모바일 관점 주목 포인트


@dataclass
class OverallInsight:
    trend_summary: str      # 경쟁사 전반 광고 트렌드
    recommendation: str     # 아이즈모바일 대응 제언 (①②③)
    urgency_level: str      # "높음" | "보통" | "낮음"


def _call_gemini(prompt: str) -> str:
    """Gemini API 호출"""
    if not GEMINI_API_KEY:
        return "(GEMINI_API_KEY 없음 — 분석 스킵)"

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 1024,
        },
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return f"(Gemini 오류: {e})"


def analyze_brand(
    brand_id: str,
    brand_name: str,
    meta_ads: list[MetaAd],
    google_ads: list[GoogleAd],
    homepage_events: list[HomepageEvent],
) -> BrandInsight:
    """브랜드별 분석"""

    # 데이터 직렬화
    meta_data = [{"text": a.ad_text, "platforms": a.platforms, "start": a.start_date} for a in meta_ads]
    google_data = [{"text": a.ad_text, "format": a.format, "platform": a.platform, "last_shown": a.last_shown} for a in google_ads]
    hp_data = [{"title": e.title, "desc": e.description, "end_date": e.end_date} for e in homepage_events]

    prompt = f"""당신은 한국 알뜰폰(MVNO) 시장 마케팅 분석가입니다.
아이즈모바일(IzsVision)의 경쟁사인 "{brand_name}"의 이번 주 광고 현황 데이터를 분석해주세요.

[Meta(페이스북·인스타그램) 광고 — {len(meta_ads)}건]
{json.dumps(meta_data, ensure_ascii=False, indent=2) if meta_data else "수집된 광고 없음"}

[Google·유튜브 광고 — {len(google_ads)}건]
{json.dumps(google_data, ensure_ascii=False, indent=2) if google_data else "수집된 광고 없음"}

[홈페이지 이벤트 — {len(homepage_events)}건]
{json.dumps(hp_data, ensure_ascii=False, indent=2) if hp_data else "수집된 이벤트 없음"}

아래 항목을 각각 2~3문장으로 분석해주세요. JSON 없이 항목별로 작성하세요.

META_SUMMARY: Meta 광고 현황 요약 (소재 특징, 메시지 톤, 집행 규모)
GOOGLE_SUMMARY: Google·유튜브 광고 현황 요약 (없으면 "집행 광고 없음"으로 작성)
HOMEPAGE_SUMMARY: 홈페이지 이벤트 현황 요약
KEY_MESSAGE: 이번 주 이 브랜드가 가장 강조하는 핵심 메시지 또는 소구 포인트 (1문장)
NOTABLE_POINT: 아이즈모바일 마케팅팀이 주목해야 할 포인트 (1~2문장)"""

    response = _call_gemini(prompt)

    def extract(label: str) -> str:
        marker = f"{label}:"
        if marker in response:
            start = response.index(marker) + len(marker)
            # 다음 라벨 또는 끝까지
            labels = ["META_SUMMARY", "GOOGLE_SUMMARY", "HOMEPAGE_SUMMARY", "KEY_MESSAGE", "NOTABLE_POINT"]
            end = len(response)
            for other in labels:
                other_marker = f"{other}:"
                if other_marker in response and response.index(other_marker) > start:
                    candidate = response.index(other_marker)
                    if candidate < end:
                        end = candidate
            return response[start:end].strip()
        return "(분석 없음)"

    return BrandInsight(
        brand_id=brand_id,
        brand_name=brand_name,
        meta_summary=extract("META_SUMMARY"),
        google_summary=extract("GOOGLE_SUMMARY"),
        homepage_summary=extract("HOMEPAGE_SUMMARY"),
        key_message=extract("KEY_MESSAGE"),
        notable_point=extract("NOTABLE_POINT"),
    )


def analyze_overall(brand_insights: list[BrandInsight]) -> OverallInsight:
    """전체 경쟁사 종합 분석"""

    summaries = "\n\n".join([
        f"[{b.brand_name}]\n"
        f"Meta: {b.meta_summary}\n"
        f"Google: {b.google_summary}\n"
        f"홈페이지: {b.homepage_summary}\n"
        f"핵심 메시지: {b.key_message}"
        for b in brand_insights
    ])

    prompt = f"""아이즈모바일(IzsVision) 마케팅팀을 위한 주간 경쟁사 광고 종합 분석을 작성해주세요.

[이번 주 경쟁사 3개사 현황 요약]
{summaries}

아래 항목을 작성해주세요.

TREND_SUMMARY: 경쟁사 전반의 광고 트렌드 및 공통적인 패턴 (3~4문장)
RECOMMENDATION: 아이즈모바일이 취해야 할 대응 방향을 ①②③ 번호로 구분하여 각 1~2문장씩 작성
URGENCY_LEVEL: 이번 주 경쟁사 움직임의 위협 수준을 "높음", "보통", "낮음" 중 하나로만 답변"""

    response = _call_gemini(prompt)

    def extract(label: str) -> str:
        marker = f"{label}:"
        if marker in response:
            start = response.index(marker) + len(marker)
            labels = ["TREND_SUMMARY", "RECOMMENDATION", "URGENCY_LEVEL"]
            end = len(response)
            for other in labels:
                other_marker = f"{other}:"
                if other_marker in response and response.index(other_marker) > start:
                    candidate = response.index(other_marker)
                    if candidate < end:
                        end = candidate
            return response[start:end].strip()
        return "(분석 없음)"

    urgency_raw = extract("URGENCY_LEVEL")
    urgency = "보통"
    for level in ["높음", "보통", "낮음"]:
        if level in urgency_raw:
            urgency = level
            break

    return OverallInsight(
        trend_summary=extract("TREND_SUMMARY"),
        recommendation=extract("RECOMMENDATION"),
        urgency_level=urgency,
    )


def run_analysis(
    meta_results: dict[str, list[MetaAd]],
    google_results: dict[str, list[GoogleAd]],
    homepage_results: dict[str, list[HomepageEvent]],
) -> tuple[list[BrandInsight], OverallInsight]:
    """전체 분석 실행"""
    print("  [Gemini] 브랜드별 분석 중...")
    brand_insights = []

    for brand in BRANDS:
        print(f"  [Gemini] {brand.name} 분석 중...")
        insight = analyze_brand(
            brand_id=brand.id,
            brand_name=brand.name,
            meta_ads=meta_results.get(brand.id, []),
            google_ads=google_results.get(brand.id, []),
            homepage_events=homepage_results.get(brand.id, []),
        )
        brand_insights.append(insight)

    print("  [Gemini] 종합 분석 중...")
    overall = analyze_overall(brand_insights)

    return brand_insights, overall
