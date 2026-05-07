# Async Listing Sync 설계

**날짜:** 2026-05-07  
**범위:** Wanted·Remember listing sync의 HTTP 클라이언트 async 전환 + `sync_all_jobs` 통합 툴 추가

---

## 배경

현재 `wanted_sync_jobs`와 `remember_sync_jobs`는 별도의 MCP 툴로 분리되어 있고 내부적으로 동기 `httpx`를 사용한다. 두 사이트를 동시에 수집할 때는 MCP 클라이언트가 순차 호출할 수밖에 없다.

이번 변경은 listing 수집 레이어를 async로 전환하여 두 사이트를 병렬로 수집하는 `sync_all_jobs` 툴을 추가한다.

**범위 밖:** `sync_job_details`의 per-job 딜레이 루프, DB 레이어(JobService) async 전환.

**포함 범위 주의:** `WantedClient`·`RememberClient`의 `fetch_applications()`도 같은 클라이언트 클래스에 존재하므로, 클라이언트를 async로 전환하면 `WantedApplicationSyncer`, `RememberApplicationSyncer`, `sync_applications` 툴도 함께 async 전환이 필요하다. 주목적은 listing sync 병렬화이지만 이 파급 변경은 불가피하다.

---

## 아키텍처

변경은 아래 레이어 순서로 "아래에서 위로" 전파된다.

```
HTTP Client (WantedClient, RememberClient)
    → Syncer (BaseSyncer, WantedSyncer, RememberSyncer)
        → 기존 Tool (wanted_sync_jobs, remember_sync_jobs)  ← async def 전환
        → 새 Tool (sync_all_jobs)                          ← asyncio.gather 병렬 실행
```

---

## 레이어별 변경 상세

### 1. HTTP Clients

**`WantedClient`**
- `__init__`에서 `self._http = httpx.AsyncClient(timeout=30)` 생성
- `_get()` → `async def _get()`: `httpx.get` → `await self._http.get`, `time.sleep` → `await asyncio.sleep`
- `fetch_jobs()`, `fetch_applications()`, `fetch_job_detail()` → `async def`, 내부 `_get()` 앞에 `await`

**`RememberClient`**
- 동일 패턴: `self._http = httpx.AsyncClient(timeout=30)`
- `fetch_jobs()`, `fetch_applications()` → `async def`, `httpx.post/get` → `await self._http.post/get`

**`AsyncClient` 수명:** 툴 호출마다 클라이언트 인스턴스를 새로 생성(단명)하므로 명시적 close 없이 GC에 위임한다.

### 2. Syncers

**`BaseSyncer`**
```python
@abstractmethod
async def sync(self, **kwargs) -> str: ...
```

**`WantedSyncer`**
```python
async def sync(self, ...) -> str:
    client = WantedClient()
    jobs = await client.fetch_jobs(...)
    ...
    return self.service.upsert_jobs(jobs, source=WANTED, full_sync=full_sync)
```

**`RememberSyncer`**
```python
async def sync(self, ...) -> str:
    client = RememberClient()
    jobs = await client.fetch_jobs(...)
    result = self.service.upsert_jobs(jobs, source=REMEMBER, full_sync=True)
    self.service.upsert_remember_details(jobs)
    return result
```

`upsert_jobs` 등 DB 쓰기는 기존 동기 SQLAlchemy 그대로 유지. asyncio는 단일 스레드이므로 두 syncer의 DB 쓰기가 실제로 겹치지 않아 충돌 없음.

### 3. 기존 툴 (wanted_sync_jobs, remember_sync_jobs)

```python
async def wanted_sync_jobs(...) -> str:
    ...
    return await WantedSyncer(service).sync(...)

async def remember_sync_jobs(...) -> str:
    ...
    return await RememberSyncer(service).sync(...)
```

파라미터·preset 처리 로직은 변경 없음.

### 4. 신규 툴: sync_all_jobs

```python
async def sync_all_jobs(
    # Wanted 파라미터
    wanted_job_group_id: int = ...,
    wanted_limit_pages: int | None = DEFAULT_LIMIT_PAGES,
    ...
    # Remember 파라미터
    remember_limit_pages: int | None = DEFAULT_LIMIT_PAGES,
    remember_job_category_names: list[dict] | None = None,
    ...
) -> str:
    engine = get_engine()
    wanted_result, remember_result = await asyncio.gather(
        WantedSyncer(JobService(engine)).sync(...),
        RememberSyncer(JobService(engine)).sync(...),
        return_exceptions=True,
    )
    # Exception → 한국어 에러 메시지로 변환
    ...
    return "[Wanted]\n{wanted_result}\n\n[Remember]\n{remember_result}"
```

**설계 결정:**
- 두 syncer에 **각각 별도 `JobService` 인스턴스** 할당 (같은 engine 공유, 별도 Session)
- `return_exceptions=True`: 한 사이트 실패 시 다른 사이트 결과 보존
- preset은 각 syncer 내부에서 기존과 동일하게 처리
- 반환 형식: `"[Wanted]\n{결과}\n\n[Remember]\n{결과}"`

---

## 에러 처리

| 상황 | 동작 |
|------|------|
| 한 사이트만 인증 실패 | 해당 사이트 결과에 에러 메시지, 나머지 정상 반환 |
| 두 사이트 모두 실패 | 각각 에러 메시지 반환 |
| `remember_job_category_names` 미지정 | Remember 결과에 기존 에러 문자열 반환 |

---

## 테스트

**기존 테스트 수정:**
- `tests/test_syncer.py`: `MagicMock` → `AsyncMock`, `def test_*` → `async def test_*`
- `tests/wanted/test_wanted_client.py`, `tests/remember/test_remember_client.py`: 클라이언트 메서드 mock `AsyncMock`으로 전환

**신규 테스트:**
- `sync_all_jobs` 정상 케이스: 두 결과 모두 반환
- `sync_all_jobs` 부분 실패: 한 쪽 예외 시 다른 쪽 결과 보존

**pytest 설정:**
- `pytest.ini` 또는 `pyproject.toml`에 `asyncio_mode = "auto"` 추가 (`@pytest.mark.asyncio` 데코레이터 생략)

**의존성:** `pytest-asyncio >= 0.23.0` 이미 requirements.txt에 존재.
