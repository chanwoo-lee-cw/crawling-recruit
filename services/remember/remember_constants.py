from enum import Enum

REMEMBER = "remember"

class RememberJobCategory(Enum):
    BACKEND_DEV = "백엔드 개발자"
    SERVER_DEV = "서버 개발자"


class RememberClientConst:
    JOBS_SEARCH_URL = "https://career-api.rememberapp.co.kr/job_postings/search"
    APPLICATIONS_URL = "https://career-api.rememberapp.co.kr/open_profiles/me/job_postings/application_histories"