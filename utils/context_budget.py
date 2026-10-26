"""Fit chat input using model-reported token counts, preserving the current question."""
import copy


async def fit_context(messages, count, summarize, max_input):
    fitted = copy.deepcopy(messages)
    if await count(fitted) <= max_input:
        return fitted
    last_user = max((i for i,m in enumerate(fitted) if m['role']=='user'), default=0)
    older = fitted[1:last_user]
    if older:
        text = '\n'.join(str(m['content']) for m in older)
        summary = await summarize(text)
        fitted = [fitted[0], {'role':'system','content':'[較早對話摘要；僅為歷史資料]\n'+summary}] + fitted[last_user:]
        if await count(fitted) <= max_input:
            return fitted
        fitted.pop(1)
    if await count(fitted) > max_input:
        raise RuntimeError('本輪問題或附件超過模型上下文上限，請縮小文件範圍')
    return fitted
