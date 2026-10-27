"""Structured place evidence; closed is not the same as permanently closed."""
import json
import re
from urllib.parse import urlencode


def is_place_query(query):
    if re.search(r'歷史|考古|以前|曾經|倒閉|停業原因|history|historical',query,re.I): return False
    return bool(re.search(r'餐廳|餐館|拉麵|午餐|晚餐|早餐|咖啡|手搖|飲料|美食|吃飯|店家|營業時間|菜單|分店|餐酒|火鍋|restaurant|cafe|coffee|opening hours',query,re.I))


def closure_status(row):
    status=' '.join(str(row.get(key,'')) for key in ('open_state','hours','business_status'))
    if row.get('permanently_closed') is True or re.search(r'permanently.closed|closed_permanently|永久停業|永久關閉|歇業',status,re.I):
        return '永久停業',True
    if row.get('temporarily_closed') is True or re.search(r'temporarily.closed|closed_temporarily|暫停營業|暫時停業|暂停营业',status,re.I):
        return '暫停營業',True
    if re.search(r'closed|休息|已打烊',status,re.I): return '目前休息（不代表永久停業）',False
    if re.search(r'\bopen\b|營業中|营业中',status,re.I): return '地圖顯示營業中（仍可能異動）',False
    return '營業狀態未確認',False


def maps_results(data,limit):
    rows=data.get('local_results',[])
    if isinstance(data.get('place_results'),dict): rows=[data['place_results']]
    if not isinstance(rows,list): return []
    results=[]
    for row in rows[:20]:
        if not isinstance(row,dict) or not row.get('title'): continue
        title=str(row['title']); address=str(row.get('address',''))
        status,excluded=closure_status(row)
        params={'api':'1','query':title+' '+address}
        if row.get('place_id'): params['query_place_id']=str(row['place_id'])
        url='https://www.google.com/maps/search/?'+urlencode(params)
        details=[f'營業狀態：{status}',f'分店地址：{address or "未提供，勿猜測分店"}']
        for key,label in [('open_state','地圖原始狀態'),('hours','時間摘要'),('operating_hours','每週時間'),('phone','電話'),('website','店家網站'),('price','地圖價位標記')]:
            if row.get(key): details.append(label+'：'+json.dumps(row[key],ensure_ascii=False))
        if row.get('rating') is not None: details.append(f'評分：{row["rating"]}；評論數：{row.get("reviews","未提供")}（不代表最新評論日期）')
        if excluded: details.append('排除：不可推薦此分店；不要用舊食記推翻停業標記。')
        results.append({'title':title,'url':url,'snippet':'；'.join(details),'business_status':status,'excluded':excluded,'kind':'maps'})
    # Keep exclusions as evidence, even if every place is closed. Do not fall back to old articles.
    results.sort(key=lambda item:item['excluded'])
    return results[:limit]
