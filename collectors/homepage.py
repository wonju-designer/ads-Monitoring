"""
홈페이지 이벤트 크롤러
각 브랜드 공식 홈페이지 이벤트 페이지를 Playwright로 동적 렌더링 후 수집합니다.
"""
import asyncio
from dataclasses import dataclass
from typing import Optional
from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout
from config import Brand, PLAYWRIGHT_TIMEOUT


@dataclass
class HomepageEvent:
    brand_id: str
    brand_name: str
    title: str
    description: str
    end_date: Optional[str]
    url: Optional[str]


# 브랜드별 파싱 전략
PARSE_STRATEGIES = {
    "freetie": {
        "wait_selector": ".event-item, [class*='eventItem'], [class*='event_item'], a[href*='/event/']",
        "item_selector": ".event-item, [class*='eventItem'], [class*='event_item']",
        "title_selector": "[class*='title'], [class*='name'], strong, h3, h4",
        "date_selector": "[class*='date'], [class*='period'], span:has-text('~'), span:has-text('까지')",
        "fallback_links": "a[href*='/event/']",
    },
    "tplus": {
        "wait_selector": "[class*='event'], .list-item, .board-item, a[href*='event']",
        "item_selector": "[class*='event-item'], .list-item, .board-item",
        "title_selector": "[class*='title'], [class*='subject'], strong, h3",
        "date_selector": "[class*='date'], [class*='period']",
        "fallback_links": "a[href*='event']",
    },
    "mobing": {
        "wait_selector": "[class*='event'], [class*='notice'], .board-list li, a[href*='event']",
        "item_selector": "[class*='event-item'], .board-list li, [class*='list-item']",
        "title_selector": "[class*='title'], [class*='subject'], strong, p",
        "date_selector": "[class*='date'], [class*='period'], span",
        "fallback_links": "a[href*='event'], a[href*='notice']",
    },
}


async def _parse_events(page: Page, brand: Brand) -> list[HomepageEvent]:
    """페이지에서 이벤트 파싱"""
    events: list[HomepageEvent] = []
    strategy = PARSE_STRATEGIES.get(brand.id, PARSE_STRATEGIES["freetie"])

    # 동적 로딩 대기
    try:
        await page.wait_for_selector(strategy["wait_selector"], timeout=10000)
        await page.wait_for_timeout(2000)
    except PWTimeout:
        # 타임아웃 시 현재 상태로 파싱 시도
        await page.wait_for_timeout(3000)

    # 이벤트 아이템 시도
    items = page.locator(strategy["item_selector"])
    count = await items.count()

    if count > 0:
        for i in range(min(count, 8)):
            item = items.nth(i)
            try:
                # 제목
                title_el = item.locator(strategy["title_selector"]).first
                title = (await title_el.inner_text(timeout=2000)).strip() if await title_el.count() > 0 else ""

                # 날짜
                date_el = item.locator(strategy["date_selector"]).first
                end_date = (await date_el.inner_text(timeout=2000)).strip() if await date_el.count() > 0 else None

                # 링크
                link_el = item.locator("a").first
                href = await link_el.get_attribute("href") if await link_el.count() > 0 else None
                if href and not href.startswith("http"):
                    base = "/".join(brand.event_url.split("/")[:3])
                    href = base + href

                # 전체 텍스트를 설명으로
                full_text = (await item.inner_text()).strip()
                description = full_text[:200] if full_text else ""

                if title or description:
                    events.append(HomepageEvent(
                        brand_id=brand.id,
                        brand_name=brand.name,
                        title=title or description[:50],
                        description=description,
                        end_date=end_date,
                        url=href,
                    ))
            except Exception:
                continue

    # 이벤트 아이템 파싱 실패 시 링크 fallback
    if not events:
        links = page.locator(strategy["fallback_links"])
        link_count = await links.count()

        for i in range(min(link_count, 8)):
            link = links.nth(i)
            try:
                text = (await link.inner_text()).strip()
                href = await link.get_attribute("href")
                if href and not href.startswith("http"):
                    base = "/".join(brand.event_url.split("/")[:3])
                    href = base + href

                if text and len(text) > 3:
                    events.append(HomepageEvent(
                        brand_id=brand.id,
                        brand_name=brand.name,
                        title=text[:100],
                        description=text[:200],
                        end_date=None,
                        url=href,
                    ))
            except Exception:
                continue

    # 최후 수단: 페이지 전체 텍스트에서 이벤트 추출
    if not events:
        try:
            body_text = await page.locator("body").inner_text()
            lines = [l.strip() for l in body_text.split("\n") if len(l.strip()) > 10]
            # 이벤트 관련 키워드가 포함된 줄 추출
            keywords = ["이벤트", "혜택", "할인", "증정", "무료", "특가", "프로모션", "%", "원"]
            event_lines = [l for l in lines if any(k in l for k in keywords)][:5]

            for line in event_lines:
                events.append(HomepageEvent(
                    brand_id=brand.id,
                    brand_name=brand.name,
                    title=line[:80],
                    description=line[:200],
                    end_date=None,
                    url=brand.event_url,
                ))
        except Exception:
            pass

    return events


async def collect_homepage_events(brands: list[Brand]) -> dict[str, list[HomepageEvent]]:
    """모든 브랜드 홈페이지 이벤트 수집"""
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
            print(f"  [Homepage] {brand.name} 이벤트 수집 중...")
            page = await context.new_page()
            try:
                await page.goto(brand.event_url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="domcontentloaded")
                events = await _parse_events(page, brand)
                results[brand.id] = events
                print(f"  [Homepage] {brand.name}: {len(events)}건 수집")
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
