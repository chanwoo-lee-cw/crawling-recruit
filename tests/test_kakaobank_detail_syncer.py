from services.kakaobank.kakaobank_detail_syncer import KakaoBankDetailSyncer

CONTENTS_HTML_FULL = """
<div class="desc_cont">
  <div class="tit"><b>담당할 업무</b></div>
  <div class="cont">
    <div class="inner_cont">
      <p>카카오뱅크 iOS 앱 서비스 개발</p>
    </div>
  </div>
</div>
<div class="desc_cont">
  <div class="tit"><b>필수 경험과 역량</b></div>
  <div class="cont">
    <div class="inner_cont">
      <p>iOS 앱 개발 4년 이상</p>
      <p>Swift 개발 가능</p>
    </div>
  </div>
</div>
<div class="desc_cont">
  <div class="tit"><b>우대사항</b></div>
  <div class="cont">
    <div class="inner_cont">
      <p>Modular Architecture 이해</p>
    </div>
  </div>
</div>
"""

CONTENTS_HTML_EMPTY = "<div></div>"


def test_parse_kakaobank_detail_extracts_sections():
    result = KakaoBankDetailSyncer._parse_kakaobank_detail(CONTENTS_HTML_FULL)
    assert "iOS 앱 개발 4년 이상" in result["requirements"]
    assert "Swift 개발 가능" in result["requirements"]
    assert "Modular Architecture" in result["preferred_points"]
    assert result["skill_tags"] == []


def test_parse_kakaobank_detail_missing_sections():
    result = KakaoBankDetailSyncer._parse_kakaobank_detail(CONTENTS_HTML_EMPTY)
    assert result["requirements"] is None
    assert result["preferred_points"] is None
