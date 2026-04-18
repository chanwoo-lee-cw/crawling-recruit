# 검색 프리셋(Search Preset) 설계

## 스키마

```
search_presets
├── id          INT PK AUTO_INCREMENT
├── name        VARCHAR(100) NOT NULL UNIQUE
├── params      JSON NOT NULL
└── created_at  DATETIME NOT NULL
```

## MCP 툴

| 툴 | 설명 | 주요 파라미터 |
|----|------|-------------|
| `save_search_preset` | 프리셋 저장/덮어쓰기 | `name`, `params` |
| `list_search_presets` | 저장된 프리셋 목록 반환 | 없음 |

## params 예시

```json
{
  "source": "wanted",
  "job_group_id": 518,
  "locations": "seoul",
  "limit_pages": 10
}
```

```json
{
  "source": "remember",
  "job_category_names": [{"level1": "SW개발", "level2": "백엔드"}],
  "min_experience": 3,
  "max_experience": 5
}
```

## ALLOWED_PRESET_KEYS

```python
{"job_group_id", "job_ids", "years", "locations", "limit_pages",
 "job_category_names", "min_experience", "max_experience", "source"}
```

## 에러 처리

| 상황 | 처리 |
|------|------|
| 허용 키 외 포함 | `ValueError("유효하지 않은 파라미터 키: ...")` → 에러 문자열 반환 |
| preset_name으로 sync_jobs 호출 시 없는 이름 | `"프리셋 '{name}'을 찾을 수 없습니다."` 반환 |
