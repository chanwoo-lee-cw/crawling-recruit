from enum import Enum

REMEMBER = "remember"

class RememberJobCategory(Enum):
    """리멤버 직무 카테고리. 값은 (level1, level2) 쌍이다.

    검색 API는 job_category_names를 {"level1": ..., "level2": ...} 형태로 받는다.
    매칭되는 카테고리가 없으면 필터를 무시하고 전 직군을 반환하므로,
    이름을 임의로 지어내면 안 된다. 전체 목록은 docs/리멤버_type.md 참고.
    """
    BACKEND = ("SW개발", "백엔드")       # id 310
    FULLSTACK = ("SW개발", "풀스택")     # id 312

    @property
    def payload(self) -> dict:
        level1, level2 = self.value
        return {"level1": level1, "level2": level2}


class RememberClientConst:
    JOBS_SEARCH_URL = "https://career-api.rememberapp.co.kr/job_postings/search"
    APPLICATIONS_URL = "https://career-api.rememberapp.co.kr/open_profiles/me/job_postings/application_histories"