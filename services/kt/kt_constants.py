KT = "kt"
KT_LIST_URL = "https://recruit.kt.com/api/recruit"
KT_JOB_BASE_URL = "https://kt.recruiter.co.kr/career/jobs"


def extract_kt_platform_id(raw: dict) -> int:
    """KT 공고의 platform_id를 뽑는다.

    recruitNoticeUrl 끝의 번호가 실제 공고 식별자이고, recruitNoticeSn은 폴백이다.
    리스트 동기화와 상세 동기화가 같은 값을 써야 매칭되므로 여기서 한 번만 정의한다.
    """
    notice_url = raw.get("recruitNoticeUrl", "")
    try:
        if notice_url and "/" in notice_url:
            return int(notice_url.rsplit("/", 1)[-1])
        return int(raw["recruitNoticeSn"])
    except (ValueError, IndexError, KeyError, TypeError):
        return int(raw.get("recruitNoticeSn") or raw.get("recruitNoticeNo", 0))
