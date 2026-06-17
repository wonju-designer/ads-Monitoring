"""
이메일 리포트 생성 및 Gmail SMTP 발송
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from config import GMAIL_USER, GMAIL_APP_PASSWORD, REPORT_TO, BRANDS
from collectors import MetaAd, GoogleAd, HomepageEvent
from analyzer import BrandInsight, OverallInsight


# ─────────────────────────────────────────
# HTML 리포트 생성
# ─────────────────────────────────────────

URGENCY_COLOR = {
    "높음": ("#fce8e6", "#b52a1a"),
    "보통": ("#fff8e1", "#856404"),
    "낮음": ("#e6f4ea", "#1e7e34"),
}


def _fmt_date_range() -> str:
    today = datetime.now()
    start = today - timedelta(days=6)
    return f"{start.strftime('%Y년 %m월 %d일')} — {today.strftime('%m월 %d일')}"


def _brand_card_html(
    brand_id: str,
    brand_name: str,
    meta_ads: list[MetaAd],
    google_ads: list[GoogleAd],
    homepage_events: list[HomepageEvent],
    insight: BrandInsight,
) -> str:
    meta_count = len(meta_ads)
    google_count = len(google_ads)
    hp_count = len(homepage_events)

    # 배지
    badges = []
    if meta_count:
        badges.append(f'<span style="background:#e8f0fe;color:#1a56b0;font-size:10px;padding:2px 8px;border-radius:20px;font-weight:500;">Meta {meta_count}건</span>')
    else:
        badges.append('<span style="background:#f1efe8;color:#888;font-size:10px;padding:2px 8px;border-radius:20px;">Meta 없음</span>')

    if google_count:
        badges.append(f'<span style="background:#fce8e6;color:#b52a1a;font-size:10px;padding:2px 8px;border-radius:20px;font-weight:500;">Google/YT {google_count}건</span>')

    if hp_count:
        badges.append(f'<span style="background:#e6f4ea;color:#1e7e34;font-size:10px;padding:2px 8px;border-radius:20px;">이벤트 {hp_count}건</span>')

    badge_html = " ".join(badges)

    # Meta 광고 소재 목록
    meta_items = ""
    for ad in meta_ads[:3]:
        platforms = "·".join(ad.platforms) if ad.platforms else "Facebook"
        meta_items += f"""
        <div style="background:#f8f7f2;border-radius:6px;padding:8px 10px;margin-bottom:6px;font-size:12px;color:#333;line-height:1.6;">
          <span style="font-size:10px;color:#888;">[{platforms}] {ad.start_date or '날짜 미상'}</span><br>
          {ad.ad_text}
        </div>"""
    if not meta_items:
        meta_items = '<p style="font-size:12px;color:#aaa;margin:0;">집행 중인 광고 없음</p>'

    # Google 광고 소재 목록
    google_items = ""
    for ad in google_ads[:3]:
        google_items += f"""
        <div style="background:#f8f7f2;border-radius:6px;padding:8px 10px;margin-bottom:6px;font-size:12px;color:#333;line-height:1.6;">
          <span style="font-size:10px;color:#888;">[{ad.platform} · {ad.format}] {ad.last_shown or ''}</span><br>
          {ad.ad_text}
        </div>"""
    if not google_items:
        google_items = '<p style="font-size:12px;color:#aaa;margin:0;">집행 중인 광고 없음</p>'

    # 홈페이지 이벤트 목록
    hp_items = ""
    for ev in homepage_events[:4]:
        end = f" (~{ev.end_date})" if ev.end_date else ""
        link = f'<a href="{ev.url}" style="color:#1a56b0;">{ev.title}</a>' if ev.url else ev.title
        hp_items += f'<div style="font-size:12px;color:#333;padding:4px 0;border-bottom:0.5px solid #f0efe8;">{link}<span style="color:#aaa;font-size:11px;">{end}</span></div>'
    if not hp_items:
        hp_items = '<p style="font-size:12px;color:#aaa;margin:0;">수집된 이벤트 없음</p>'

    return f"""
    <div style="border:0.5px solid #e8e7e0;border-radius:8px;margin-bottom:16px;overflow:hidden;">
      <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 16px;background:#fafaf8;border-bottom:0.5px solid #e8e7e0;">
        <span style="font-size:14px;font-weight:500;color:#1a1a1a;">{brand_name}</span>
        <div style="display:flex;gap:6px;">{badge_html}</div>
      </div>
      <div style="padding:16px;">

        <table style="width:100%;border-collapse:collapse;">
          <tr>
            <td style="vertical-align:top;padding-right:12px;width:50%;">
              <p style="font-size:11px;font-weight:500;color:#888;margin:0 0 8px;letter-spacing:0.05em;">META 광고 소재</p>
              {meta_items}
            </td>
            <td style="vertical-align:top;width:50%;">
              <p style="font-size:11px;font-weight:500;color:#888;margin:0 0 8px;letter-spacing:0.05em;">GOOGLE · 유튜브 광고</p>
              {google_items}
            </td>
          </tr>
        </table>

        <div style="margin-top:12px;">
          <p style="font-size:11px;font-weight:500;color:#888;margin:0 0 8px;letter-spacing:0.05em;">홈페이지 이벤트</p>
          {hp_items}
        </div>

        <div style="background:#f0efe8;border-radius:6px;padding:10px 12px;margin-top:12px;">
          <p style="font-size:11px;color:#888;margin:0 0 4px;">💡 아이즈모바일 관점</p>
          <p style="font-size:12px;color:#333;margin:0;line-height:1.7;">{insight.notable_point}</p>
        </div>

      </div>
    </div>"""


def build_html_report(
    meta_results: dict[str, list[MetaAd]],
    google_results: dict[str, list[GoogleAd]],
    homepage_results: dict[str, list[HomepageEvent]],
    brand_insights: list[BrandInsight],
    overall: OverallInsight,
) -> str:
    date_range = _fmt_date_range()
    today = datetime.now().strftime("%Y년 %m월 %d일")

    # 통계
    total_meta = sum(len(v) for v in meta_results.values())
    total_google = sum(len(v) for v in google_results.values())
    total_hp = sum(len(v) for v in homepage_results.values())

    urgency_bg, urgency_text = URGENCY_COLOR.get(overall.urgency_level, URGENCY_COLOR["보통"])

    # 브랜드 카드
    brand_cards = ""
    for brand in BRANDS:
        insight = next((i for i in brand_insights if i.brand_id == brand.id), None)
        if not insight:
            continue
        brand_cards += _brand_card_html(
            brand_id=brand.id,
            brand_name=brand.name,
            meta_ads=meta_results.get(brand.id, []),
            google_ads=google_results.get(brand.id, []),
            homepage_events=homepage_results.get(brand.id, []),
            insight=insight,
        )

    # 대응 제언 (줄바꿈 처리)
    rec_html = overall.recommendation.replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>경쟁사 광고 모니터링 주간 리포트</title>
</head>
<body style="margin:0;padding:0;background:#f5f5f3;font-family:'Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR',sans-serif;">

<div style="max-width:640px;margin:24px auto;background:#ffffff;border-radius:10px;overflow:hidden;border:0.5px solid #e0dfd8;">

  <!-- 헤더 -->
  <div style="background:#1a1a1a;padding:28px 32px;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
      <span style="font-size:13px;font-weight:500;color:#fff;letter-spacing:0.05em;">아이즈모바일 · 경쟁사 광고 모니터링</span>
      <span style="font-size:11px;color:#888;background:#2a2a2a;padding:3px 10px;border-radius:20px;">주간 리포트</span>
    </div>
    <div style="font-size:20px;font-weight:500;color:#fff;margin-bottom:4px;">경쟁사 광고 현황 리포트</div>
    <div style="font-size:13px;color:#888;">{date_range} · 자동 수집 기준</div>
  </div>

  <!-- 핵심 요약 -->
  <div style="padding:24px 32px;border-bottom:0.5px solid #f0efe8;">
    <p style="font-size:11px;font-weight:500;color:#888;letter-spacing:0.06em;margin:0 0 12px;">이번 주 핵심 요약</p>
    <div style="background:#f8f7f2;border-radius:8px;padding:16px 18px;border-left:3px solid #1a1a1a;">
      <p style="font-size:13px;color:#1a1a1a;line-height:1.8;margin:0;">{overall.trend_summary}</p>
    </div>
    <div style="display:inline-block;margin-top:10px;background:{urgency_bg};color:{urgency_text};font-size:11px;font-weight:500;padding:4px 12px;border-radius:20px;">
      위협 수준: {overall.urgency_level}
    </div>
  </div>

  <!-- 수집 현황 -->
  <div style="padding:20px 32px;border-bottom:0.5px solid #f0efe8;">
    <p style="font-size:11px;font-weight:500;color:#888;letter-spacing:0.06em;margin:0 0 12px;">수집 현황</p>
    <table style="width:100%;border-collapse:collapse;">
      <tr>
        <td style="width:33%;padding-right:8px;">
          <div style="background:#f8f7f2;border-radius:8px;padding:14px 16px;">
            <p style="font-size:11px;color:#888;margin:0 0 6px;">Meta 광고 소재</p>
            <p style="font-size:22px;font-weight:500;color:#1a1a1a;margin:0;">{total_meta}</p>
            <p style="font-size:11px;color:#aaa;margin:4px 0 0;">페이스북·인스타그램</p>
          </div>
        </td>
        <td style="width:33%;padding:0 4px;">
          <div style="background:#f8f7f2;border-radius:8px;padding:14px 16px;">
            <p style="font-size:11px;color:#888;margin:0 0 6px;">Google·유튜브 광고</p>
            <p style="font-size:22px;font-weight:500;color:#1a1a1a;margin:0;">{total_google}</p>
            <p style="font-size:11px;color:#aaa;margin:4px 0 0;">Ads Transparency</p>
          </div>
        </td>
        <td style="width:33%;padding-left:8px;">
          <div style="background:#f8f7f2;border-radius:8px;padding:14px 16px;">
            <p style="font-size:11px;color:#888;margin:0 0 6px;">홈페이지 이벤트</p>
            <p style="font-size:22px;font-weight:500;color:#1a1a1a;margin:0;">{total_hp}</p>
            <p style="font-size:11px;color:#aaa;margin:4px 0 0;">공식 홈페이지 기준</p>
          </div>
        </td>
      </tr>
    </table>
  </div>

  <!-- 브랜드별 상세 -->
  <div style="padding:24px 32px;border-bottom:0.5px solid #f0efe8;">
    <p style="font-size:11px;font-weight:500;color:#888;letter-spacing:0.06em;margin:0 0 14px;">브랜드별 상세 현황</p>
    {brand_cards}
  </div>

  <!-- 대응 제언 -->
  <div style="padding:24px 32px;border-bottom:0.5px solid #f0efe8;">
    <p style="font-size:11px;font-weight:500;color:#888;letter-spacing:0.06em;margin:0 0 12px;">아이즈모바일 대응 제언</p>
    <div style="background:#1a1a1a;border-radius:8px;padding:18px 20px;">
      <p style="font-size:13px;color:#cccccc;line-height:1.85;margin:0;">{rec_html}</p>
    </div>
  </div>

  <!-- 푸터 -->
  <div style="padding:20px 32px;background:#fafaf8;">
    <p style="font-size:11px;color:#aaa;line-height:1.8;margin:0;">
      이 리포트는 매주 월요일 오전 9시에 자동 발송됩니다.<br>
      수집 채널: Meta Ad Library · Google Ads Transparency Center (SerpApi) · 브랜드 공식 홈페이지<br>
      수집 기준일: {today}
    </p>
  </div>

</div>
</body>
</html>"""


# ─────────────────────────────────────────
# Gmail SMTP 발송
# ─────────────────────────────────────────

def send_report(html_content: str) -> bool:
    """Gmail SMTP로 리포트 발송"""
    if not all([GMAIL_USER, GMAIL_APP_PASSWORD, REPORT_TO]):
        print("  [Email] 환경변수 누락 — 발송 스킵 (GMAIL_USER / GMAIL_APP_PASSWORD / REPORT_TO)")
        # 로컬 확인용 HTML 파일 저장
        with open("report_preview.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("  [Email] report_preview.html 로 저장됨")
        return False

    today = datetime.now().strftime("%Y.%m.%d")
    subject = f"[아이즈모바일] 경쟁사 광고 현황 주간 리포트 — {today}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = REPORT_TO
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, REPORT_TO.split(","), msg.as_string())
        print(f"  [Email] 발송 완료 → {REPORT_TO}")
        return True
    except Exception as e:
        print(f"  [Email] 발송 실패: {e}")
        return False
