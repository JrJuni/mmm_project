# mmm-search-mcp (한국어)

Google Trends의 국가별 검색 수요를 마케팅 믹스 모델링(MMM)용 타겟 시장 뷰로
바꿔주는 작고 읽기 전용인 데이터 도구입니다. 개발·추적 인프라가 빈약한
중소기업(SMB)을 염두에 두고 만들었습니다.

비용이 드는 수집기 1개, 읽기 표면 2개(정적 그리드 + MCP 서버), 그 사이를 잇는
캐시 JSON 파일 1개로 구성됩니다.

> 영문 문서가 source of truth입니다. 이 파일은 한국어 companion이며, 관리자가
> 한국어 갱신을 요청할 때 함께 업데이트합니다.

## 무엇을 하나

- 추적 키워드(기본값 `Arencia`)의 국가별 검색 관심도를 SerpApi를 통해 Google
  Trends에서 수집합니다.
- 현재 주 / 직전 주 값과 주간 증감(WoW)을 `data/data.json`에 캐시합니다.
- 4열 국가 그리드(`web/index.html`)를 **대륙 / 검색 관심도 / 주간 증감** 색으로
  렌더링합니다. 주식 시세판 같은 형태이되, 박스 크기 매핑은 가독성을 위해
  의도적으로 뺐습니다.
- 읽기 전용 MCP 도구를 노출해, 쓰던 챗봇에서 바로 질문할 수 있습니다
  ("어느 시장이 앞서나?", "대륙별로 요약").

## 무엇이 아닌가

- 절대 검색량이 아닙니다. Trends는 0~100 상대 지수를 줍니다. 국가별 절대량
  (타겟 시장 선정·MMM 회귀 입력에 더 적합)이 필요하면 Keyword Planner나 Glimpse로
  데이터 소스를 교체하세요. 코드에 교체용 어댑터 seam이 하나 있습니다.
- 실시간 피드가 아닙니다. 갱신 주기는 데이터가 실제로 변하는 속도(Trends는
  주 단위)에 맞춰 cron으로 정합니다.
- 쓰기/자동화 시스템이 아닙니다. MCP 표면은 설계상 읽기 전용입니다.

## 구조 요약

```
cron ─▶ collector/fetch_data.py ─▶ data/data.json ─┬─▶ web/index.html (그리드)
        (유일한 SerpApi 호출자)        (캐시)          └─▶ mcp_server/server.py (읽기 전용 도구)
```

핵심 불변식: **SerpApi를 호출하는 건 수집기뿐입니다.** 그리드와 MCP 서버는
캐시만 읽으므로 호출량이 무료·무제한이고, 과금되는 사용량은 cron 주기로만
고정됩니다. 자세한 내용은 [`docs/architecture.md`](docs/architecture.md).

## 이 형태로 만든 이유

SMB에 흔한 제약들에서 출발했습니다.

- `pytrends`는 유지보수가 중단됐고(2025년 4월 아카이브), 봇으로 감지되면 조용히
  변조된 데이터를 줄 수 있어 MMM 회귀 입력으로 위험합니다.
- 공식 Google Trends API는 alpha·초대제이고 쿼터가 빡빡합니다.
- 직접 스크래핑은 봇 차단됩니다. 유료 API(SerpApi, Glimpse)가 바로 그 문제를
  풀어주며, 키워드 1개 정도는 무료 티어로 충분합니다.

그래서 데이터 소스를 교체 가능한 함수 하나 뒤에 두고, 캐시를 적극적으로 써서
비용을 묶고, 보안 표면을 최소화하기 위해 읽기 전용을 유지합니다. 보안 모델은
[`docs/security.md`](docs/security.md).

## 설치

### 준비물

- Python 3.11+
- SerpApi 계정 + 무료 API 키 (https://serpapi.com/manage-api-key)
- MCP 클라이언트(Claude Desktop, Codex/ChatGPT)

### 절차

```bash
git clone https://github.com/JrJuni/mmm_project
cd mmm_project
python -m pip install -r requirements.txt

cp .env.example .env       # .env를 열어 SERPAPI_KEY를 로컬에만 입력
python -m collector.fetch_data        # 최초 수집 -> data/data.json
python -m http.server 8000            # 레포 루트 서빙
# http://localhost:8000/web/index.html 열기
```

키가 아직 없다면, 번들된 샘플로 비용 없이 그리드를 볼 수 있습니다.

```bash
cp data/data.sample.json data/data.json
```

### 수집 스케줄 (cron, 매일)

```cron
0 6 * * * cd /path/to/mmm_project && /usr/bin/python -m collector.fetch_data >> collect.log 2>&1
```

### MCP 서버 연결

```bash
python -m mcp_server.server
```

연결 후 챗봇에게 먼저 `config_doctor` 실행을 요청하세요.

## 도구 안내

모든 도구는 읽기 전용이고 SerpApi 쿼터를 소모하지 않습니다.

- `config_doctor` — 캐시 존재·가독성·신선도 점검. 가장 먼저 실행.
- `get_search_data` — 국가별 전체 표(코드, 대륙, 관심도, 직전값, 증감%).
- `get_top_markets(n=5)` — 관심도 상위 N개국(타겟 후보).
- `get_continent_summary` — 대륙별 합계/평균/국가 수.

## 비용·무료티어 계산

```
월 호출수 = 키워드 수 x 기간 수 x 하루 갱신 횟수 x 30
기본값    = 1         x 2       x 1            x 30 = 약 60
무료 예산 = 월 약 100회(보수적)
```

무료 티어를 넘는 건 키워드를 늘리거나 갱신을 잦게 할 때입니다. UI 새로고침과
모든 MCP 호출은 무료입니다. `collector/config.py`에서 조정하세요.

## 자주 묻는 질문

**왜 박스 크기가 다 같나요?** 0~100 상대 지수에 크기를 비례시키면 오해를 줍니다
(시가총액이 아니므로). 대신 색이 신호를 담고, "Shade by" 토글로 대륙/관심도/증감을
전환합니다.

**챗봇이 데이터를 갱신할 수 있나요?** 아니요(설계상). 갱신은 스케줄 작업(또는
수집기를 직접 돌리는 비공개 관리 작업)이지 MCP 도구가 아닙니다. 비용·유출 채널을
닫아두기 위함입니다.

**MMM에 지수로 충분한가요?** 모니터링·타겟 선정에는 충분합니다. 회귀 입력으로는
절대량(Keyword Planner/Glimpse)이 상대 스케일 문제를 피해 더 깔끔합니다. 어댑터
seam 덕분에 교체가 국소적입니다.

## 라이선스

MIT. 수정본 재배포 시 라이선스와 출처 표기를 유지하세요.
