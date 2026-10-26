from utils.search_grounding import ground_answer


def test_unsupported_map_link_loses_only_url():
    assert ground_answer("[查看地圖](https://maps.google.com/?q=fake)", "地址：臺北市大安區和平路1號") == "查看地圖（來源未確認）"


def test_supported_url_with_parentheses_and_encoding():
    text = "[來源](https://example.com/shop_(one)) [另一頁](https://example.com/a%28b%29)"
    assert ground_answer(text, "https://example.com/shop_(one) https://example.com/a%28b%29") == text


def test_wrong_district_address_replaced_but_citation_retained():
    result = ground_answer("地址：台北市信義區和平東路三段123號 [來源](https://example.com/shop)", "臺北市大安區和平東路三段123號 https://example.com/shop")
    assert "信義區" not in result
    assert "完整地址未經來源確認，請參閱來源頁面" in result
    assert "[來源](https://example.com/shop)" in result


def test_address_normalizes_tai_and_whitespace():
    text = "地址：台北市大安區和平東路三段123號"
    assert ground_answer(text, "臺北市 大安區 和平東路三段 123號") == text


def test_prose_and_code_unchanged():
    text = "推薦先看菜單。\n```python\naddress = '台北市信義區信義路1號'\nurl = '[x](https://fake.example)'\n```"
    assert ground_answer(text, "nothing") == text


def test_url_prefix_does_not_count_as_source():
    assert ground_answer("[來源](https://example.com/shop)", "https://example.com/shopping") == "來源（來源未確認）"


def test_supported_address_in_prose_keeps_intro():
    answer = "店家位於台北市大安區和平東路三段123號，建議先預約。"
    assert ground_answer(answer, "臺北市大安區和平東路三段123號") == answer


def test_supported_markdown_url_title():
    answer = '[官網](<https://example.com/shop> "店家官網")'
    assert ground_answer(answer, '[店家](https://example.com/shop)') == answer
