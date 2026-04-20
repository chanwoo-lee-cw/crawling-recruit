# Daily Sync Cron Job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 매일 오후 10시에 crontab으로 sync_jobs → sync_job_details → sync_applications 전체 파이프라인을 자동 실행하는 스크립트를 만든다.

**Architecture:** `scripts/daily_sync.py`가 `tools/*.py` 함수를 직접 import해서 순서대로 호출한다. 각 단계는 try/except로 감싸 실패해도 다음 단계가 실행된다. 소스 목록은 `SOURCES` 리스트로 관리해 추후 사이트 추가가 쉽다.

**Tech Stack:** Python 3.11, python-dotenv, crontab

---

## File Structure

- **Create:** `scripts/daily_sync.py` — 전체 파이프라인 러너
- **Create:** `tests/test_daily_sync.py` — 러너 유닛 테스트
- **Modify:** `.gitignore` — `logs/` 추가

---

### Task 1: .gitignore에 logs/ 추가

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: `.gitignore`에 `logs/` 라인 추가**

`.gitignore` 파일 맨 아래에 추가:
```
logs/
```

- [ ] **Step 2: 커밋**

```bash
git add .gitignore
git commit -m "chore: logs/ 디렉토리 gitignore 추가"
```

---

### Task 2: daily_sync.py 테스트 작성 (TDD)

**Files:**
- Create: `tests/test_daily_sync.py`

기존 테스트 패턴(`tests/test_tools.py`)을 따라 `unittest.mock.patch`로 각 tools 함수를 모킹한다.

- [ ] **Step 1: 테스트 파일 생성**

```python
# tests/test_daily_sync.py
import pytest
from unittest.mock import patch, call


def test_run_calls_sync_jobs_for_each_source():
    """SOURCES의 각 소스에 대해 sync_jobs가 호출되는지 확인"""
    with patch("scripts.daily_sync.sync_jobs") as mock_sync_jobs, \
         patch("scripts.daily_sync.sync_job_details") as mock_details, \
         patch("scripts.daily_sync.sync_applications") as mock_apps:

        mock_sync_jobs.return_value = "동기화 완료: 10개"
        mock_details.return_value = "상세 10개 수집"
        mock_apps.return_value = "완료"

        from scripts.daily_sync import run
        run()

    assert mock_sync_jobs.call_count == 2
    calls = mock_sync_jobs.call_args_list
    assert calls[0] == call(source="wanted")
    assert calls[1] == call(
        source="remember",
        job_category_names=[{"name": "백엔드 개발자"}, {"name": "서버 개발자"}],
    )
    mock_details.assert_called_once()
    assert mock_apps.call_count == 2  # wanted + remember


def test_run_skips_job_details_if_all_sync_jobs_fail():
    """모든 sync_jobs가 실패하면 sync_job_details를 실행하지 않는다"""
    with patch("scripts.daily_sync.sync_jobs", side_effect=Exception("API 오류")), \
         patch("scripts.daily_sync.sync_job_details") as mock_details, \
         patch("scripts.daily_sync.sync_applications"):

        from scripts.daily_sync import run
        run()

    mock_details.assert_not_called()


def test_run_continues_after_sync_jobs_partial_failure():
    """일부 sync_jobs가 실패해도 성공한 소스가 있으면 sync_job_details를 실행한다"""
    call_count = 0

    def side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("wanted 오류")
        return "동기화 완료: 5개"

    with patch("scripts.daily_sync.sync_jobs", side_effect=side_effect), \
         patch("scripts.daily_sync.sync_job_details") as mock_details, \
         patch("scripts.daily_sync.sync_applications"):

        from scripts.daily_sync import run
        run()

    mock_details.assert_called_once()


def test_run_continues_after_sync_job_details_failure():
    """sync_job_details가 실패해도 sync_applications는 실행된다"""
    with patch("scripts.daily_sync.sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.sync_job_details", side_effect=Exception("상세 오류")), \
         patch("scripts.daily_sync.sync_applications") as mock_apps:

        from scripts.daily_sync import run
        run()

    assert mock_apps.call_count >= 1
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

```bash
pytest tests/test_daily_sync.py -v
```

Expected: `ModuleNotFoundError: No module named 'scripts.daily_sync'`

---

### Task 3: scripts/daily_sync.py 구현

**Files:**
- Create: `scripts/__init__.py` (빈 파일)
- Create: `scripts/daily_sync.py`

- [ ] **Step 1: `scripts/__init__.py` 생성**

```python
# scripts/__init__.py
```

- [ ] **Step 2: `scripts/daily_sync.py` 구현**

```python
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from tools.sync_jobs import sync_jobs
from tools.sync_job_details import sync_job_details
from tools.sync_applications import sync_applications

SOURCES = ["wanted", "remember"]

SYNC_CONFIG = {
    "wanted": {},
    "remember": {
        "job_category_names": [
            {"name": "백엔드 개발자"},
            {"name": "서버 개발자"},
        ],
    },
}


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run():
    log("=== daily sync start ===")

    synced_count = 0
    for source in SOURCES:
        try:
            kwargs = SYNC_CONFIG.get(source, {})
            result = sync_jobs(source=source, **kwargs)
            log(f"sync_jobs({source}): {result}")
            synced_count += 1
        except Exception as e:
            log(f"sync_jobs({source}): 오류 - {e}")

    if synced_count == 0:
        log("모든 sync_jobs 실패 - sync_job_details 스킵")
    else:
        try:
            result = sync_job_details()
            log(f"sync_job_details: {result}")
        except Exception as e:
            log(f"sync_job_details: 오류 - {e}")

    for source in SOURCES:
        try:
            result = sync_applications(source=source)
            log(f"sync_applications({source}): {result}")
        except Exception as e:
            log(f"sync_applications({source}): 오류 - {e}")

    log("=== daily sync end ===")


if __name__ == "__main__":
    run()
```

- [ ] **Step 3: 테스트 실행해서 통과 확인**

```bash
pytest tests/test_daily_sync.py -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 4: 전체 테스트 회귀 확인**

```bash
pytest
```

Expected: 기존 테스트 포함 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add scripts/__init__.py scripts/daily_sync.py tests/test_daily_sync.py
git commit -m "feat: daily sync cron runner 스크립트 추가"
```

---

### Task 4: logs/ 디렉토리 및 crontab 등록

**Files:**
- Create: `logs/.gitkeep`

- [ ] **Step 1: `logs/` 디렉토리 생성**

```bash
mkdir -p logs && touch logs/.gitkeep
```

- [ ] **Step 2: 수동 실행으로 동작 확인**

```bash
cd /Users/chanwoo/PycharmProjects/crawling-recruit
.venv/bin/python scripts/daily_sync.py
```

Expected: 터미널에 로그 출력, 에러 없음

- [ ] **Step 3: crontab 등록**

```bash
crontab -e
```

다음 라인 추가 (프로젝트 경로 확인 후 입력):
```
0 22 * * * cd /Users/chanwoo/PycharmProjects/crawling-recruit && .venv/bin/python scripts/daily_sync.py >> logs/daily_sync.log 2>&1
```

- [ ] **Step 4: crontab 등록 확인**

```bash
crontab -l
```

Expected: 위 라인이 출력됨

- [ ] **Step 5: 커밋**

```bash
git add logs/.gitkeep
git commit -m "chore: logs 디렉토리 추가"
```
