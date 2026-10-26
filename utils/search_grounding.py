"""Conservative checks for source URLs and concrete Taiwan addresses.

This is best-effort output grounding, not verification of other factual claims.
It deliberately performs no network requests and logs no answer or query content.
"""

import re


_CODE = re.compile(r"(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`)")
_URL = re.compile(r"https?://[^\s<>\"'\[\]]+")
_ADDRESS = re.compile(
    r"(?:[台臺]北市|新北市|桃園市|[台臺]中市|[台臺]南市|高雄市|"
    r"基隆市|新竹[市縣]|嘉義[市縣]|宜蘭縣|苗栗縣|彰化縣|南投縣|"
    r"雲林縣|屏東縣|花蓮縣|[台臺]東縣|澎湖縣|金門縣|連江縣)\s*"
    r"[\u4e00-\u9fff]{1,4}[區鄉鎮市]\s*"
    r"[\u4e00-\u9fff0-9０-９\s]{1,45}?[路街大道]"
    r"[\u4e00-\u9fff0-9０-９\s之\-]{0,30}?號"
    r"(?:之[0-9０-９]+)?(?:\s*[0-9０-９一二三四五六七八九十]+樓)?"
)


def _normalize(text):
    return re.sub(r"\s+", "", text).replace("台", "臺")


def _trim_url(url):
    url = url.rstrip(".,;，。；！!?？")
    # An evidence URL may be wrapped in Markdown; preserve balanced URL parentheses.
    while url.endswith(")") and url.count(")") > url.count("("):
        url = url[:-1]
    return url


def _ground_links(text, urls):
    """Read balanced link destinations rather than truncating URLs at their first ')'."""
    pattern = re.compile(r"\[([^\]\n]+)\]\(")
    output = []
    cursor = 0
    for match in pattern.finditer(text):
        if match.start() < cursor:
            continue
        pos, depth = match.end(), 1
        while pos < len(text) and depth:
            if text[pos] == "\\":
                pos += 2
                continue
            if text[pos] == "(":
                depth += 1
            elif text[pos] == ")":
                depth -= 1
            pos += 1
        if depth:
            continue
        destination = text[match.end():pos - 1].strip()
        # Markdown allows an angle-wrapped destination and an optional quoted title.
        if destination.startswith("<") and ">" in destination:
            url = destination[1:destination.index(">")]
        else:
            url = destination.split()[0] if destination else ""
        url = url.replace("\\(", "(").replace("\\)", ")")
        output.append(text[cursor:match.start()])
        output.append(text[match.start():pos] if url in urls else f"{match.group(1)}（來源未確認）")
        cursor = pos
    output.append(text[cursor:])
    return "".join(output)


def ground_answer(answer: str, evidence: str) -> str:
    """Remove unsupported Markdown URLs and full city/district/street addresses.

    Call only for answers based on actual web-search evidence. Code is preserved.
    Source URL membership is exact; addresses allow whitespace and 台/臺 variants.
    Prices, hours, names and other factual claims are outside this narrow check.
    """
    urls = {_trim_url(match.group()) for match in _URL.finditer(evidence)}
    normalized_evidence = _normalize(evidence)
    parts = _CODE.split(answer)
    for index in range(0, len(parts), 2):
        text = _ground_links(parts[index], urls)
        parts[index] = _ADDRESS.sub(
            lambda match: match.group() if _normalize(match.group()) in normalized_evidence
            else "完整地址未經來源確認，請參閱來源頁面",
            text,
        )
    return "".join(parts)
