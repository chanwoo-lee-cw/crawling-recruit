from enum import Enum

WANTED = "wanted"

class JobSort(Enum):
    LATEST_ORDER = "job.latest_order"
    RECOMMEND_ORDER = "job.recommend_order"
    POPULARITY_ORDER = "job.popularity_order"