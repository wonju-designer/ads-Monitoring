# 경쟁사 광고 현황 모니터링 시스템

아이즈모바일 경쟁사(프리티·티플러스·모빙) 광고 현황을 매주 자동 수집·분석·이메일 발송하는 시스템입니다.

## 수집 채널
- **Meta Ad Library** — 페이스북·인스타그램 광고 소재 (Playwright)
- **Google Ads Transparency Center** — 유튜브·구글 광고 소재 (SerpApi)
- **홈페이지 이벤트** — 각 브랜드 공식 홈페이지 이벤트 페이지 (Playwright)

## 분석
- Gemini API (gemini-2.0-flash)

## 발송
- Gmail SMTP → 매주 월요일 오전 9시 자동 실행 (GitHub Actions)

## 디렉토리 구조
```
ad-monitor/
├── .github/
│   └── workflows/
│       └── weekly_report.yml   # GitHub Actions 스케줄
├── collectors/
│   ├── meta.py                 # Meta Ad Library 크롤링
│   ├── google_ads.py           # SerpApi Google Ads Transparency
│   └── homepage.py             # 홈페이지 이벤트 크롤링
├── analyzer.py                 # Gemini API 분석
├── reporter.py                 # 이메일 리포트 생성·발송
├── main.py                     # 진입점
├── config.py                   # 브랜드·설정 정의
├── requirements.txt
└── README.md
```

## 환경변수 (GitHub Secrets)
| 변수명 | 설명 |
|---|---|
| `SERPAPI_KEY` | SerpApi API 키 |
| `GEMINI_API_KEY` | Google Gemini API 키 |
| `GMAIL_USER` | 발송용 Gmail 주소 |
| `GMAIL_APP_PASSWORD` | Gmail 앱 비밀번호 |
| `REPORT_TO` | 리포트 수신 이메일 주소 |

## 로컬 실행
```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env  # 환경변수 입력 후
python main.py
```
