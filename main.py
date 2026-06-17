"""
경쟁사 광고 현황 모니터링 — 메인 진입점
실행: python main.py
"""
import asyncio
import sys
from datetime import datetime
from config import BRANDS
from collectors import collect_meta_ads, collect_google_ads, collect_homepage_events
from analyzer import run_analysis
from reporter import build_html_report, send_report


async def main():
    start = datetime.now()
    print(f"\n{'='*50}")
    print(f"경쟁사 광고 모니터링 시작 — {start.strftime('%Y-%m-%d %H:%M')}")
    print(f"대상 브랜드: {', '.join(b.name for b in BRANDS)}")
    print(f"{'='*50}\n")

    # ── 1. 수집 ───────────────────────────────────
    print("[1/3] 데이터 수집")

    print("\n  Meta Ad Library 수집 중...")
    meta_results = await collect_meta_ads(BRANDS)

    print("\n  Google Ads Transparency 수집 중...")
    google_results = collect_google_ads(BRANDS)

    print("\n  홈페이지 이벤트 수집 중...")
    homepage_results = await collect_homepage_events(BRANDS)

    # 수집 요약
    print("\n  ── 수집 결과 ──")
    for brand in BRANDS:
        m = len(meta_results.get(brand.id, []))
        g = len(google_results.get(brand.id, []))
        h = len(homepage_results.get(brand.id, []))
        print(f"  {brand.name}: Meta {m}건 | Google {g}건 | 홈페이지 {h}건")

    # ── 2. 분석 ───────────────────────────────────
    print("\n[2/3] Gemini 분석")
    brand_insights, overall_insight = run_analysis(
        meta_results, google_results, homepage_results
    )

    # ── 3. 리포트 생성 및 발송 ────────────────────
    print("\n[3/3] 리포트 생성 및 발송")
    html = build_html_report(
        meta_results, google_results, homepage_results,
        brand_insights, overall_insight,
    )
    success = send_report(html)

    elapsed = (datetime.now() - start).seconds
    print(f"\n{'='*50}")
    print(f"완료 — 소요 시간: {elapsed}초 | 발송: {'성공' if success else '스킵/실패'}")
    print(f"{'='*50}\n")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
