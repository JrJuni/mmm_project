# Lessons learned

Append-only log. Newest entries on top. One entry per stumble or decision worth
not repeating. Format: **Date / Tried / Result / Lesson / Related**.

---

## 2026-06-24 — Test the grid at its real served URL, not just the file

- **Tried:** The Python checks simulated the grid's display logic against the
  `data/data.json` file directly, and all passed.
- **Result:** Rendering the page the documented way
  (`python -m http.server` at repo root, open `/web/index.html`) showed nothing:
  the relative `fetch('data/data.json')` resolved to `/web/data/data.json`
  (404). The cache lives at `/data/data.json`. Confirmed with a headless Edge
  screenshot.
- **Lesson:** Simulating the data path in Python does not exercise browser URL
  resolution. For a static page that `fetch()`es a sibling directory, test the
  actual served URL. Fixed to `../data/data.json`; a headless screenshot is a
  cheap way to verify the real render.
- **Related:** `web/index.html` (fetch path), `AI_START_HERE.md` (serving note).

## 2026-06-24 — Verify quota numbers against the live pricing page

- **Tried:** Budgeted the collector against "~100 searches/month", taken from a
  pasted AI research summary; flagged 100-vs-250 as uncertain.
- **Result:** The real SerpApi free plan is **250 searches/month, 50/hour**,
  confirmed on the live [pricing page](https://serpapi.com/pricing) and the
  user's own account dashboard. The "100" (and a "20/hour") figures were stale.
- **Lesson:** For cost-bearing limits, confirm against the vendor's live pricing
  page (and the actual dashboard) before encoding them — secondary summaries
  drift. Set `config.monthly_quota_budget` from the verified number (now 250).
- **Related:** `collector/config.py`, README "Free-tier terms (SerpApi)".

## 2026-06-24 — SerpApi `now 14-d` is not a valid date

- **Tried:** First live collector run with the shipped default config
  (`previous_timeframe = "now 14-d"` to get a prior-week window).
- **Result:** HTTP 400 `{"error": "Invalid date format."}` on the second call.
  The first call (`now 7-d`) returned 109 rows; only `now 14-d` failed, so the
  collector could never complete a two-period run. The error handler correctly
  left the existing cache untouched.
- **Lesson:** SerpApi google_trends `date` relative tokens only support
  `now 1-H/4-H/1-d/7-d` (and `today 1-m/3-m/12-m`, `today 5-y`, `all`). There is
  no `now 14-d`. To compare two equal windows, use explicit
  `YYYY-MM-DD YYYY-MM-DD` ranges (now via `config.window_days` +
  `CollectorConfig.timeframes()`); both windows then share length and
  granularity, which makes the week-over-week delta meaningful.
- **Related:** `collector/config.py:timeframes()`, `collector/fetch_data.py`,
  `docs/architecture.md` (adapter seam).

## 2026-06-24 — `.env` was documented but never loaded

- **Tried:** Put the SerpApi key in `.env` (as `.env.example` and the collector
  error message instruct) and run `python -m collector.fetch_data`.
- **Result:** Key ignored — the collector read only `os.environ`; nothing parsed
  `.env` (collector is intentionally stdlib-only, no python-dotenv).
- **Lesson:** If docs tell users to use `.env`, the code must actually load it.
  Added a tiny stdlib `.env` parser (`_load_dotenv` in `config.py`) using
  `os.environ.setdefault` so a real environment variable still wins. Kept the
  parser deliberately minimal (no export/multiline/interpolation).
- **Related:** `collector/config.py:_load_dotenv()`, `.env.example`.

---

## Blind Review 판정 누적

### 최종 판정 로그 — P1 런타임 검증 plan (라운드 1, 2026-06-24)

외부 AI(unknown, 보안·corner-case 지향)가 plan `env-playful-falcon.md`를 리뷰.

| # | 카테고리 | 판정 | 사유 |
|---|---|---|---|
| 1 | corner-case | accepted | 라이브 콜 전 무네트워크 로더 검증 Step 추가 (로드/우선순위/부재) |
| 2 | corner-case | accepted | 보안 step에 64-hex 키 누출 grep + `git check-ignore` 명세 |
| 3 | corner-case | refined | 음성 캐시 테스트를 env override+해시 비교로, `.env` 편집 금지·선택화 |
| 4 | over-engineering | refined | 웹 검증을 정적 grep으로 (headless 브라우저는 과함, 기각) |
| 5 | documentation | accepted | 라이브 전 repo/branch/python/deps preflight + 메타 캡처 |
| 6 | style | accepted | 로더 파서 스펙 명확화 + 파서 비목표 명시 |

**메타:** 보안·corner-case 발견 우수. 약점: 일부 over-reach(headless), step5를
"truncated"로 약간 오기재.
**Skeptic 결과:** 미실행 — 사용자가 "v2 작성 후 진행" 의사로 fresh skeptic 생략.
라운드 1 단발 리뷰로 종료, 실제 실행에서 plan 검증됨(추가 버그 1건 발견·수정).
