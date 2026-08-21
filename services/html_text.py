"""채용공고 상세 HTML을 읽을 수 있는 텍스트로 바꾸는 공용 유틸.

여러 소스(KT, CJ 등)가 문장을 인라인 <span>으로 잘게 쪼개 놓기 때문에
BeautifulSoup의 get_text(strip=True)를 그대로 쓰면 단어가 붙거나 조각난다.
말단 블록 요소 단위로 끊고, 블록 안에서는 공백만 정리한다.
"""
import re

from bs4 import BeautifulSoup
from bs4.element import Tag

BLOCK_TAGS = ["p", "li", "td", "h1", "h2", "h3", "h4", "h5", "h6", "div", "tr", "section"]
_WHITESPACE = re.compile(r"[\s\xa0]+")


def to_lines(node: Tag | str) -> list[str]:
    """말단 블록 요소마다 한 줄씩. 블록이 하나도 없으면 전체를 한 줄로."""
    root = BeautifulSoup(node, "html.parser") if isinstance(node, str) else node
    lines = []
    for el in root.find_all(BLOCK_TAGS):
        if el.find(BLOCK_TAGS):  # 컨테이너는 건너뛰고 말단만
            continue
        text = _clean(el)
        if text:
            lines.append(text)
    if not lines:
        text = _clean(root)
        if text:
            lines.append(text)
    return lines


def to_text(node: Tag | str) -> str:
    return "\n".join(to_lines(node))


def _clean(el: Tag) -> str:
    # strip=True는 텍스트 노드마다 공백을 없애 단어를 붙여버리므로 쓰지 않는다
    return _WHITESPACE.sub(" ", el.get_text("")).strip()
