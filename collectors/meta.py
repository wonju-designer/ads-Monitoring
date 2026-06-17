"""
Meta Ad Library 크롤러
facebook.com/ads/library 에서 경쟁사 광고 소재를 수집합니다.
"""
import asyncio
import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout
from config import Brand, META_AD_LIBRARY_URL, MAX_ADS_PER_BRAND, PLAYWRIGHT_TIMEOUT


@dataclass
class MetaAd:
    brand_id: str
    brand_name: str
    ad_text: str
    start_date: Optional[str]
    platforms: list[str]
    status: str                  # "active" | "inactive"
    ad_id: Optional[str] = None
    image_url: Optional[str] = None


async def _search_brand(page: Page, brand: Brand) -> list[MetaAd]:
    """단일 브랜드 Meta Ad Library 검색"""
    ads: list[MetaAd] = []

    try:
        url = (
            f"{META_AD_LIBRARY_URL}"
            f"?active_status=active"
            f"&ad_type=all"
            f"&country=KR"
            f"&q={brand.meta_advertiser_name}"
            f"&search_type=keyword_unordered"
            f"&media_type=all"
        )

        await page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        # 쿠키 동의 팝업 처리
        for selector in ["[data-testid='cookie-policy-manage-dialog-accept-button']",
                         "button:has-text('Allow')", "button:has-text('수락')"]:
            try:
                btn = page.locator(selector).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await page.wait_for_timeout(1500)
                    break
            except Exception:
                pass

        # 광고 카드 수집
        ad_cards = page.locator("[data-testid='ad-archive-render-ad-card'], ._7jyg, [class*='adCard']")
        count = min(await ad_cards.count(), MAX_ADS_PER_BRAND)

        for i in range(count):
            card = ad_cards.nth(i)
            try:
                # 광고 텍스트
                text_el = card.locator("[data-testid='ad-archive-preview-text'], ._4bl9, [class*='body']").first
                ad_text = (await text_el.inner_text(timeout=3000)).strip() if await text_el.count() > 0 else ""

                # 날짜
                date_el = card.locator("text=/\\d{4}년|started running/i").first
                start_date = (await date_el.inner_text(timeout=2000)).strip() if await date_el.count() > 0 else None

                # 플랫폼
                platforms = []
                for platform in ["Facebook", "Instagram", "Audience Network", "Messenger"]:
                    try:
                        p_el = card.locator(f"text={platform}").first
                        if await p_el.count() > 0:
                            platforms.append(platform)
                    except Exception:
                        pass

                # 이미지
                img_el = card.locator("img").first
                image_url = await img_el.get_attribute("src") if await img_el.count() > 0 else None

                if ad_text or start_date:
                    ads.append(MetaAd(
                        brand_id=brand.id,
                        brand_name=brand.name,
                        ad_text=ad_text[:300] if ad_text else "(텍스트 없음)",
                        start_date=start_date,
                        platforms=platforms if platforms else ["Facebook"],
                        status="active",
                        image_url=image_url,
                    ))
            except Exception:
                continue

        # 광고가 없는 경우 결과 없음 체크
        if not ads:
            no_result = page.locator("text=/결과가 없|no results|No ads/i").first
            if await no_result.count() > 0:
                print(f"  [Meta] {brand.name}: 집행 중인 광고 없음")
            else:
                print(f"  [Meta] {brand.name}: 광고 파싱 실패 (페이지 구조 변경 가능성)")

    except PWTimeout:
        print(f"  [Meta] {brand.name}: 타임아웃")
    except Exception as e:
        print(f"  [Meta] {brand.name}: 오류 — {e}")

    return ads


async def collect_meta_ads(brands: list[Brand]) -> dict[str, list[MetaAd]]:
    """모든 브랜드 Meta 광고 수집"""
    results: dict[str, list[MetaAd]] = {}

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
            print(f"  [Meta] {brand.name} 수집 중...")
            page = await context.new_page()
            try:
                ads = await _search_brand(page, brand)
                results[brand.id] = ads
                print(f"  [Meta] {brand.name}: {len(ads)}건 수집")
            finally:
                await page.close()
            await asyncio.sleep(2)

        await browser.close()

    return results
