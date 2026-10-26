import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock


def test_long_attachment_summary_receives_tail_instead_of_cutting_it(monkeypatch):
    from utils import attachment_reader as reader
    content='前文' * 7000 + '文件末尾的重要結論'
    monkeypatch.setattr(reader,'parse_document',AsyncMock(return_value=content))
    summary=AsyncMock(return_value='完整分段摘要：包含文件末尾的重要結論')
    att=SimpleNamespace(filename='long.txt',size=10,content_type='text/plain',read=AsyncMock(return_value=b'data'))
    parts=asyncio.run(reader.build_attachment_parts('總結文件',[att],summarize=summary))
    assert summary.call_args.args[0]==content
    assert '文件末尾的重要結論' in parts[1]['text']
    assert '內容已截斷' not in parts[1]['text']


def test_chunk_summary_reads_every_chunk_and_merges(handler,monkeypatch):
    seen=[]
    async def generate(system,text,max_tokens=512):
        seen.append(text)
        return '摘要：'+text[-50:]
    monkeypatch.setattr(handler,'_document_completion',generate,raising=False)
    text='A'*4000+'B'*4000+'TAIL-CONCLUSION'
    answer=asyncio.run(handler.summarize_document(text,'請總結'))
    assert len(seen)>=3
    assert any('TAIL-CONCLUSION' in part for part in seen)
    assert 'TAIL-CONCLUSION' in answer


def test_scanned_pdf_is_read_with_local_vision_instead_of_rejected(monkeypatch):
    from utils import attachment_reader as reader
    monkeypatch.setattr(reader,'parse_document',AsyncMock(return_value={'images':['aW1hZ2U='],'pages':1}))
    vision=AsyncMock(return_value='第1頁辨識文字：驗收日期六月十八日')
    att=SimpleNamespace(filename='scan.pdf',size=10,content_type='application/pdf',read=AsyncMock(return_value=b'pdf'))
    parts=asyncio.run(reader.build_attachment_parts('總結',[att],read_scanned=vision))
    vision.assert_awaited_once()
    assert '驗收日期六月十八日' in parts[1]['text']


def test_incomplete_document_output_is_not_reported_as_fully_read(handler,monkeypatch):
    import pytest
    handler._gemini_quota_exceeded=True
    async def stream(*args,**kwargs):
        yield ('部分文字',None,'length')
    monkeypatch.setattr(handler,'_stream_lmstudio_sse',stream)
    with pytest.raises(RuntimeError,match='完整'):
        asyncio.run(handler._document_completion('辨識文件','資料'))


def test_full_supported_document_range_preserves_final_chunk(handler,monkeypatch):
    seen=[]
    async def generate(system,text,max_tokens=512):
        seen.append(text)
        return text[-40:]
    monkeypatch.setattr(handler,'_document_completion',generate)
    source='A'*(200000-len('TAIL-CONCLUSION'))+'TAIL-CONCLUSION'
    answer=asyncio.run(handler.summarize_document(source,'請摘要'))
    assert len(seen)==50
    assert 'TAIL-CONCLUSION' in answer


def test_mixed_pdf_preserves_text_and_renders_image_only_pages():
    import pymupdf
    from utils.attachment_reader import parse_document
    pdf=pymupdf.open()
    page=pdf.new_page(); page.insert_text((50,50),'Typed section')
    page=pdf.new_page(); page.draw_rect(pymupdf.Rect(30,30,100,100),fill=(0,0,0))
    data=pdf.tobytes(); pdf.close()
    result=asyncio.run(parse_document('mixed.pdf',data))
    assert 'Typed section' in result['text']
    assert [image['page'] for image in result['images']]==[2]
