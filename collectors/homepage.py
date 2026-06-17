"""
홈페이지 이벤트 크롤러
각 브랜드 공식 홈페이지 이벤트 페이지를 Playwright로 동적 렌더링 후 수집합니다.
- 최근 1주일 이내 이벤트만 수집
- 공지사항 제외, 이벤트만 수집
"""
import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout
from config import Brand, PLAYWRIGHT_TIMEOUT


@dataclass
class HomepageEvent:
    brand_id: str
    brand_name: str
    title: str
    description: str
    start_date: Optional[str]
    end_date: Optional[str]
    url: Optional[str]


# 날짜 파싱 헬퍼
def _parse_date(text: str) -> Optional[datetime]:
    """다양한 날짜 형식 파싱"""
    if not text:
        return None
    text = text.strip()
    patterns = [
        r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})',   # 2026.06.10 / 2026-06-10
        r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일',      # 2026년 6월 10일
        r'(\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})',     # 26.06.10
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 2000
            try:
                return datetime(y, mo, d)
            except ValueError:
                continue
    return None


def _is_within_week(date_str: Optional[str], allow_ongoing: bool = True) -> bool:
    """날짜가 최근 1주일 이내이거나 진행 중인지 확인"""
    if not date_str:
        # 날짜 없으면 일단 포함 (진행 중 가정)
        return allow_ongoing

    now = datetime.now()
    week_ago = now - timedelta(days=7)

    # "~날짜" 형식이면 종료일 기준
    end_match = re.search(r'[~\-]\s*(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})', date_str)
    if end_match:
        end_dt = _parse_date(end_match.group(1))
        if end_dt:
            # 종료일이 오늘 이후면 진행 중 → 포함
            return end_dt >= now

    # 시작일 기준: 최근 7일 이내
    dt = _parse_date(date_str)
    if dt:
        return dt >= week_ago

    return allow_ongoing


# ─────────────────────────────────────────
# 브랜드별 파싱 전략
# ─────────────────────────────────────────
PARSE_STRATEGIES = {
    "freetie": {
        "url": "https://www.freet.co.kr/event/ongoing/list",
        "wait_selector": "a[href*='/event/'], [class*='event']",
        "item_selector": "[class*='eventItem'], [class*='event-item'], [class*='event_item']",
        "title_selector": "[class*='title'], [class*='name'], strong, h3, h4",
        "date_selector": "[class*='date'], [class*='period'], span:has-text('~'), span:has-text('까지')",
        "fallback_links": "a[href*='/event/detail'], a[href*='/event/view']",
        "exclude_keywords": ["공지", "안내", "점검", "변경"],
    },
    "tplus": {
        "url": "https://www.tplusmobile.com/main/event/event?eventtp=ing",
        "wait_selector": "[class*='event'], .event-list, ul li a",
        "item_selector": "[class*='event-item'], [class*='eventItem'], .event-list li, ul.list li",
        "title_selector": "[class*='title'], [class*='tit'], p, span, strong",
        "date_selector": "[class*='date'], [class*='period'], [class*='term']",
        "fallback_links": "a[href*='event']",
        "exclude_keywords": ["공지", "FAQ", "자주묻는"],
    },
    "mobing": {
        "url": "https://www.mobing.co.kr/event",
        "wait_selector": "[class*='event'], a[href*='/event/view']",
        "item_selector": "[class*='event-item'], [class*='eventItem'], li:has(a[href*='/event/view'])",
        "title_selector": "[class*='title'], [class*='tit'], p, strong",
        "date_selector": "[class*='date'], [class*='period'], span:has-text('~')",
        "fallback_links": "a[href*='/event/view']",
        "exclude_keywords": ["공지사항", "notice", "안내", "점검"],
    },
}


async def _parse_brand_events(page: Page, brand: Brand) -> list[HomepageEvent]:
    strategy = PARSE_STRATEGIES.get(brand.id, PARSE_STRATEGIES["freetie"])
    events: list[HomepageEvent] = []
    exclude_kw = strategy.get("exclude_keywords", [])
    base_url = "/".join(strategy["url"].split("/")[:3])

    # 동적 로딩 대기
    try:
        await page.wait_for_selector(strategy["wait_selector"], timeout=12000)
        await page.wait_for_timeout(2500)
    except PWTimeout:
        await page.wait_for_timeout(3000)

    # 1차: 이벤트 아이템 선택자로 수집
    items = page.locator(strategy["item_selector"])
    count = await items.count()

    if count > 0:
        for i in range(min(count, 15)):
            item = items.nth(i)
            try:
                full_text = (await item.inner_text()).strip()

                # 공지사항 제외
                if any(kw in full_text for kw in exclude_kw):
                    continue

                # 제목
                title_el = item.locator(strategy["title_selector"]).first
                title = (await title_el.inner_text(timeout=2000)).strip() if await title_el.count() > 0 else full_text[:60]

                # 날짜
                date_el = item.locator(strategy["date_selector"]).first
                date_text = (await date_el.inner_text(timeout=2000)).strip() if await date_el.count() > 0 else ""

                # 링크
                link_el = item.locator("a").first
                href = await link_el.get_attribute("href") if await link_el.count() > 0 else None
                if href and not href.startswith("http"):
                    href = base_url + href

                # 날짜 필터: 최근 1주일 or 진행 중
                if not _is_within_week(date_text):
                    continue

                if title and len(title) > 3:
                    events.append(HomepageEvent(
                        brand_id=brand.id,
                        brand_name=brand.name,
                        title=title[:100],
                        description=full_text[:200],
                        start_date=None,
                        end_date=date_text or None,
                        url=href,
                    ))
            except Exception:
                continue

    # 2차: 링크 fallback
    if not events:
        links = page.locator(strategy["fallback_links"])
        link_count = await links.count()

        for i in range(min(link_count, 15)):
            link = links.nth(i)
            try:
                text = (await link.inner_text()).strip()
                if not text or len(text) <= 3:
                    continue
                if any(kw in text for kw in exclude_kw):
                    continue

                href = await link.get_attribute("href")
                if href and not href.startswith("http"):
                    href = base_url + href

                # 부모 요소에서 날짜 찾기
                parent = link.locator("xpath=..")
                parent_text = (await parent.inner_text()).strip()
                date_text = ""
                date_match = re.search(r'\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}', parent_text)
                if date_match:
                    date_text = date_match.group(0)

                if not _is_within_week(date_text):
                    continue

                events.append(HomepageEvent(
                    brand_id=brand.id,
                    brand_name=brand.name,
                    title=text[:100],
                    description=parent_text[:200],
                    start_date=None,
                    end_date=date_text or None,
                    url=href,
                ))
            except Exception:
                continue

    # 3차: 페이지 텍스트에서 키워드 기반 추출 (최후 수단)
    if not events:
        try:
            body_text = await page.locator("body").inner_text()
            lines = [l.strip() for l in body_text.split("\n") if len(l.strip()) > 10]
            keywords = ["이벤트", "혜택", "할인", "증정", "무료", "특가", "프로모션"]
            excl = ["공지", "FAQ", "안내", "점검"]
            event_lines = [
                l for l in lines
                if any(k in l for k in keywords) and not any(e in l for e in excl)
            ][:5]

            for line in event_lines:
                events.append(HomepageEvent(
                    brand_id=brand.id,
                    brand_name=brand.name,
                    title=line[:80],
                    description=line[:200],
                    start_date=None,
                    end_date=None,
                    url=strategy["url"],
                ))
        except Exception:
            pass

    return events


async def collect_homepage_events(brands: list[Brand]) -> dict[str, list[HomepageEvent]]:
    """모든 브랜드 홈페이지 이벤트 수집 (최근 1주일 이내 + 진행 중만)"""
    results: dict[str, list[HomepageEvent]] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            locale="ko-KR",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

        for brand in brands:
            strategy = PARSE_STRATEGIES.get(brand.id, {})
            url = strategy.get("url", brand.event_url)
            print(f"  [Homepage] {brand.name} 이벤트 수집 중... ({url})")
            page = await context.new_page()
            try:
                await page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="domcontentloaded")
                events = await _parse_brand_events(page, brand)
                results[brand.id] = events
                print(f"  [Homepage] {brand.name}: {len(events)}건 수집 (1주일 이내 + 진행 중)")
            except PWTimeout:
                print(f"  [Homepage] {brand.name}: 타임아웃")
                results[brand.id] = []
            except Exception as e:
                print(f"  [Homepage] {brand.name}: 오류 — {e}")
                results[brand.id] = []
            finally:
                await page.close()

            await asyncio.sleep(2)

        await browser.close()

    return results
