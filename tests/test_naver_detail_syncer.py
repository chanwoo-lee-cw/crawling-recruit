from services.naver.naver_detail_syncer import NaverDetailSyncer

DETAIL_HTML_FULL = """
<html><body>
<div class="detail_wrap">
  <div class="detail_box">
    <div class="detail_togglebox">
      <div class="detail_toggletitle">
        <h4 class="detail_title">자격요건</h4>
      </div>
      <div class="detail_toggleinfo">
        <p class="detail_text">Python 3년 이상</p>
      </div>
    </div>
  </div>
  <div class="detail_box">
    <div class="detail_togglebox">
      <div class="detail_toggletitle">
        <h4 class="detail_title">우대사항</h4>
      </div>
      <div class="detail_toggleinfo">
        <p class="detail_text">FastAPI 경험 우대</p>
      </div>
    </div>
  </div>
</div>
</body></html>
"""

DETAIL_HTML_NO_HEADINGS = """
<html><body>
<div class="detail_wrap">
  <div class="detail_box">
    <h4 class="detail_title"></h4>
    <p class="detail_text">공고 내용 전체</p>
  </div>
</div>
</body></html>
"""

DETAIL_HTML_EMPTY = "<html><body></body></html>"


def test_parse_naver_detail_with_sections():
    result = NaverDetailSyncer._parse_naver_detail(DETAIL_HTML_FULL)
    assert "Python 3년" in result["requirements"]
    assert "FastAPI" in result["preferred_points"]
    assert result["skill_tags"] == []


def test_parse_naver_detail_fallback_when_no_headings():
    result = NaverDetailSyncer._parse_naver_detail(DETAIL_HTML_NO_HEADINGS)
    assert result["requirements"] is not None
    assert "공고 내용 전체" in result["requirements"]
    assert result["preferred_points"] is None


def test_parse_naver_detail_empty_html():
    result = NaverDetailSyncer._parse_naver_detail(DETAIL_HTML_EMPTY)
    assert result["requirements"] is None
    assert result["preferred_points"] is None
    assert result["skill_tags"] == []
