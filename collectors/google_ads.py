"""
Google Ads Transparency Center 수집기
SerpApi를 통해 유튜브·구글 광고 소재를 수집합니다.
무료 플랜: 월 100건 (브랜드 3개 × 주 1회 × 4주 = 12건으로 충분)
"""
import urllib.request
import urllib.parse
import json
from dataclasses import dataclass
from typing import Optional
from config import Brand, SERPAPI_KEY, MAX_ADS_PER_BRAND


@dataclass
class GoogleAd:
    brand_id: str
    brand_name: str
    ad_text: str
    advertiser_name: str
    last_shown: Optional[str]
    format: str              # "VIDEO" | "IMAGE" | "TEXT"
    platform: str            # "YouTube" | "Search" | "Display"
    ad_url: Optional[str] = None


def _call_serpapi(params: dict) -> dict:
    """SerpApi 호출"""
    params["api_key"] = SERPAPI_KEY
    params["engine"] = "google_ads_transparency_center"
    query = urllib.parse.urlencode(params)
    url = f"https://serpapi.com/search.json?{query}"

    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"    [SerpApi] API 호출 오류: {e}")
        return {}


def _parse_ads(data: dict, brand: Brand) -> list[GoogleAd]:
    """SerpApi 응답 파싱"""
    ads: list[GoogleAd] = []

    # ads_transparency_results 또는 organic_results 키 확인
    raw_ads = (
        data.get("ads_transparency_results") or
        data.get("results") or
        []
    )

    for item in raw_ads[:MAX_ADS_PER_BRAND]:
        # 광고 포맷 판별
        fmt = "TEXT"
        if item.get("video_url") or item.get("type", "").upper() == "VIDEO":
            fmt = "VIDEO"
        elif item.get("image_url") or item.get("type", "").upper() == "IMAGE":
            fmt = "IMAGE"

        # 플랫폼 판별
        platform = "Search"
        if fmt == "VIDEO":
            platform = "YouTube"
        elif item.get("format", "").lower() in ["display", "banner"]:
            platform = "Display"

        # 광고 텍스트 조합
        headline = item.get("headline") or item.get("title") or ""
        description = item.get("description") or item.get("body") or ""
        ad_text = f"{headline} / {description}".strip(" /") or "(내용 없음)"

        ads.append(GoogleAd(
            brand_id=brand.id,
            brand_name=brand.name,
            ad_text=ad_text[:300],
            advertiser_name=item.get("advertiser_name", brand.google_advertiser_name),
            last_shown=item.get("last_shown") or item.get("date"),
            format=fmt,
            platform=platform,
            ad_url=item.get("ad_url") or item.get("url"),
        ))

    return ads


def collect_google_ads(brands: list[Brand]) -> dict[str, list[GoogleAd]]:
    """모든 브랜드 Google 광고 투명성 센터 수집"""
    results: dict[str, list[GoogleAd]] = {}

    if not SERPAPI_KEY:
        print("  [Google ATC] SERPAPI_KEY 없음 — 스킵")
        for brand in brands:
            results[brand.id] = []
        return results

    for brand in brands:
        print(f"  [Google ATC] {brand.name} 수집 중...")
        ads: list[GoogleAd] = []

        # 1차: 브랜드명으로 검색
        data = _call_serpapi({
            "query": brand.google_advertiser_name,
            "region": "KR",
        })
        ads = _parse_ads(data, brand)

        # 2차: 도메인으로 재검색 (1차 결과 없을 때)
        if not ads and brand.google_domain:
            data = _call_serpapi({
                "query": brand.google_domain,
                "region": "KR",
            })
            ads = _parse_ads(data, brand)

        # 3차: 한글 브랜드명으로 재검색
        if not ads and brand.name != brand.google_advertiser_name:
            data = _call_serpapi({
                "query": brand.name,
                "region": "KR",
            })
            ads = _parse_ads(data, brand)

        results[brand.id] = ads
        print(f"  [Google ATC] {brand.name}: {len(ads)}건 수집")

    return results
