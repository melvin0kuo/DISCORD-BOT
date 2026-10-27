"""Bound individual responses independently of repetition or user intent."""
import re
import unicodedata


def response_limits(question):
    if re.search(r'鏡頭|镜头|字幕|故事|擬聲|拟声',question):return (4000,80)
    technical=bool(re.search(r'文件|附件|摘要|分析|程式|代碼|代码|debug|python|java|rust|code',question,re.I))
    return (8000,160) if technical else (4000,80)


def oversized_request(question):
    text=unicodedata.normalize('NFKC',question)
    characters,lines=response_limits(text)
    # Require a generation verb immediately before the size, rather than
    # mistaking the size of an input document for requested output length.
    for match in re.finditer(r'(?:製作|生成|寫|写|輸出|输出|列出|給我|给我|提供)\s*(?:一篇|一份|共|總共|約|至少|完整的)?\s*([\d,]+)\s*(字|行|個鏡頭|个镜头|個項目|个项目)',text):
        size=int(match[1].replace(',',''))
        if size>(characters if match[2]=='字' else lines):return True
    return False
