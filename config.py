import os
from dataclasses import dataclass, field
from typing import Optional

# ─────────────────────────────────────────
# 환경변수
# ─────────────────────────────────────────
SERPAPI_KEY       = os.getenv("SERPAPI_KEY", "")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
GMAIL_USER        = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
REPORT_TO         = os.getenv("REPORT_TO", "")

# ─────────────────────────────────────────
# 브랜드 정의
# ─────────────────────────────────────────
@dataclass
class Brand:
    id: str
    name: str
    # Meta Ad Library
    meta_advertiser_name: str           # 검색할 광고주명
    meta_page_name: Optional[str]       # Facebook 페이지명 (없으면 None)
    # SerpApi Google Ads Transparency
    google_advertiser_name: str         # 구글 광고 투명성 검색어
    google_domain: Optional[str]        # 브랜드 도메인 (있으면 더 정확)
    # 홈페이지 이벤트
    event_url: str                      # 이벤트 페이지 URL
    event_selector: str                 # 이벤트 목록 CSS 선택자


BRANDS: list[Brand] = [
    Brand(
        id="freetie",
        name="프리티",
        meta_advertiser_name="프리티",
        meta_page_name="freetmobile",
        google_advertiser_name="프리텔레콤",
        google_domain="freet.co.kr",
        event_url="https://www.freet.co.kr/event/ongoing/list",
        event_selector=".event-list-wrap, .event_list, [class*='event']",
    ),
    Brand(
        id="tplus",
        name="티플러스",
        meta_advertiser_name="티플러스",
        meta_page_name=None,
        google_advertiser_name="한국케이블텔레콤",
        google_domain="tplusmobile.com",
        event_url="https://www.tplusmobile.com/event/list",
        event_selector="[class*='event'], .board-list, .list-wrap",
    ),
    Brand(
        id="mobing",
        name="모빙",
        meta_advertiser_name="모빙",
        meta_page_name=None,
        google_advertiser_name="유니컴즈",
        google_domain="mobing.co.kr",
        event_url="https://www.mobing.co.kr/notice/event",
        event_selector="[class*='event'], [class*='notice'], .board-list",
    ),
]

# ─────────────────────────────────────────
# 수집 설정
# ─────────────────────────────────────────
META_AD_LIBRARY_URL = "https://www.facebook.com/ads/library/"
GOOGLE_ATC_URL      = "https://adstransparency.google.com/"
MAX_ADS_PER_BRAND   = 5    # 브랜드당 최대 수집 광고 수
PLAYWRIGHT_TIMEOUT  = 30000  # ms

# ─────────────────────────────────────────
# Gemini 설정
# ─────────────────────────────────────────
GEMINI_MODEL = "gemini-2.0-flash"
