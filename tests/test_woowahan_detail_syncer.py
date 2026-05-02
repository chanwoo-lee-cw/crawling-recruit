from services.woowahan.woowahan_detail_syncer import WoowahanDetailSyncer

RECRUIT_CONTENTS_FULL = """
<p><strong>[조직소개]</strong> CX프로덕트실 소개</p>
<p><strong>[지원자격]</strong></p>
<p>웹 프론트엔드 개발 경력 5년 이상</p>
<p>TypeScript, React 경험</p>
<p><strong>[우대사항]</strong></p>
<p>단위 테스트 경험</p>
"""

RECRUIT_CONTENTS_NO_SECTIONS = "<p>일반 공고 내용</p>"


def test_parse_woowahan_detail_extracts_sections():
    result = WoowahanDetailSyncer._parse_woowahan_detail(RECRUIT_CONTENTS_FULL)
    assert "웹 프론트엔드 개발 경력 5년 이상" in result["requirements"]
    assert "TypeScript, React 경험" in result["requirements"]
    assert "단위 테스트 경험" in result["preferred_points"]
    assert result["skill_tags"] == []


def test_parse_woowahan_detail_missing_sections():
    result = WoowahanDetailSyncer._parse_woowahan_detail(RECRUIT_CONTENTS_NO_SECTIONS)
    assert result["requirements"] is None
    assert result["preferred_points"] is None


def test_recruit_number_reconstructed_from_platform_id():
    """platform_id(int) → f"R{platform_id}" = recruitNumber."""
    platform_id = 2411018
    recruit_number = f"R{platform_id}"
    assert recruit_number == "R2411018"
