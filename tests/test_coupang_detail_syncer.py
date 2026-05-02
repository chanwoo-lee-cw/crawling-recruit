from services.coupang.coupang_detail_syncer import CoupangDetailSyncer

DETAIL_HTML_FULL = """
<html><body>
<div class="main-col">
  <article class="cms-content">
    <div><strong>자격 요건</strong></div>
    <ul>
      <li>Python 3년 이상</li>
      <li>AWS 경험</li>
    </ul>
    <div><strong>우대 사항</strong></div>
    <ul>
      <li>FastAPI 경험 우대</li>
    </ul>
  </article>
</div>
</body></html>
"""

DETAIL_HTML_NO_SECTIONS = """
<html><body>
<div class="main-col">
  <article class="cms-content">
    <p>공고 내용입니다.</p>
  </article>
</div>
</body></html>
"""

DETAIL_HTML_EMPTY = "<html><body></body></html>"


def test_parse_coupang_detail_with_sections():
    result = CoupangDetailSyncer._parse_coupang_detail(DETAIL_HTML_FULL)
    assert "Python 3년 이상" in result["requirements"]
    assert "AWS 경험" in result["requirements"]
    assert "FastAPI 경험 우대" in result["preferred_points"]
    assert result["skill_tags"] == []


def test_parse_coupang_detail_missing_sections_returns_none():
    result = CoupangDetailSyncer._parse_coupang_detail(DETAIL_HTML_NO_SECTIONS)
    assert result["requirements"] is None
    assert result["preferred_points"] is None


def test_parse_coupang_detail_empty_html():
    result = CoupangDetailSyncer._parse_coupang_detail(DETAIL_HTML_EMPTY)
    assert result["requirements"] is None
    assert result["preferred_points"] is None
    assert result["skill_tags"] == []
