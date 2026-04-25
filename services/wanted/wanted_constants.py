from enum import Enum

WANTED = "wanted"

class WantedJobSort(Enum):
    LATEST_ORDER = "job.latest_order"
    RECOMMEND_ORDER = "job.recommend_order"
    POPULARITY_ORDER = "job.popularity_order"


class WantedJobGroupId(Enum):
    SERVER_DEVELOPER = 518


class WantedClientConst:
    JOBS_API_URL = "https://www.wanted.co.kr/api/chaos/navigation/v1/results"
    APPS_API_URL = "https://www.wanted.co.kr/api/v1/applications"
    DETAIL_API_URL = "https://www.wanted.co.kr/api/chaos/jobs/v4/{job_id}/details"
    MAX_RETRIES = 3