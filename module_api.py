import requests
import re
import json
import io
from PIL import Image
import google.generativeai as genai

def download_img(url):
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        res.raise_for_status()
        return Image.open(io.BytesIO(res.content)).convert("RGB")
    except: return None

def extract_item_id(url):
    match = re.search(r'offer/(\d+)', url)
    if not match: match = re.search(r'(\d{10,14})', url)
    return match.group(1) if match else None

def fetch_1688_item_api(item_id, rapid_key):
    if not str(item_id).startswith("abb-"):
        item_id = f"abb-{item_id}"
        
    headers = {"X-RapidAPI-Key": rapid_key, "X-RapidAPI-Host": "otapi-1688.p.rapidapi.com"}
    
    # [수술 부위] 공장장님의 원본 코드에서 오직 홈페이지에서 성공했던 파라미터 규칙만 적용했습니다.
    params = {"itemId": item_id, "language": "en"}
    
    # 공장장님의 원본 엔드포인트 3개를 그대로 복구했습니다.
    endpoints = [
        "https://otapi-1688.p.rapidapi.com/GetItemFullInfo",
        "https://otapi-1688.p.rapidapi.com/GetItem",
        "https://otapi-1688.p.rapidapi.com/BatchGetItemFullInfo"
    ]
    
    last_err = ""
    for ep in endpoints:
        try:
            resp = requests.get(ep, headers=headers, params=params, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ErrorCode") == "Ok": return data.get("Result", {}).get("Item", {}), None
                else: last_err = data.get("ErrorDescription", f"API 내부 에러: {data.get('ErrorCode')}")
            else: last_err = f"상태코드 {resp.status_code}: {resp.text[:100]}"
        except Exception as e: last_err = str(e)
    return None, f"호출 실패. (사유: {last_err})"

def convert_api_to_v9_dict(api_item):
    d = {"sku_list": [], "product_title": api_item.get('Title', ''), "attributes": {"소재": "상세페이지 참조", "사이즈": "프리사이즈", "무게": "500"}, "main_imgs": [], "sku_imgs": [], "detail_imgs": [], "category": ""}
    for attr in api_item.get('Attributes', []):
        name = str(attr.get('PropertyName', '')).lower()
        val = str(attr.get('Value', ''))
        if any(kw in name for kw in ['재질', '재료', '소재', 'material']): d['attributes']['소재'] = val
        if any(kw in name for kw in ['무게', '중량', 'weight']):
            num = re.search(r'([\d\.]+)', val)
            if num:
                v = float(num.group(1))
                d['attributes']['무게'] = str(int(v * 1000 if v < 10 else v))
                
    d['main_imgs'] = [p.get('Url') for p in api_item.get('Pictures', []) if p.get('Url')]
    d['detail_imgs'] = re.findall(r'src=["\'](http[^"\']+)["\']', api_item.get('Description', ''))
    fallback_img = d['main_imgs'][0] if d['main_imgs'] else ""
    
    skus = api_item.get('ConfiguredItems', [])
    if skus:
        for sku in skus:
            opt_name = " ".join([str(c.get('Vid', '')) for c in sku.get('Configurators', [])])
            price_dict = sku.get('Price', {})
            price = price_dict.get('OriginalPrice', 0) if isinstance(price_dict, dict) else price_dict
            d['sku_list'].append({"옵션명": opt_name, "위안화": float(price), "이미지": fallback_img})
    else:
        price_dict = api_item.get('Price', {})
        price = price_dict.get('OriginalPrice', 0) if isinstance(price_dict, dict) else price_dict
        d['sku_list'].append({"옵션명": "단일색상 FREE", "위안화": float(price), "이미지": fallback_img})
    return d

def get_color_from_image_ai(api_key, img_url):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        img = download_img(img_url)
        if img:
            prompt = "이 상품의 주된 색상을 딱 하나의 한국어 단어로 말해줘 (예: 화이트, 블랙, 우드, 투명, 실버, 레드, 블루, 그린, 옐로우, 핑크, 그레이, 베이지, 브라운, 네이비, 차콜). 다른 설명은 절대 하지마."
            res = model.generate_content([prompt, img]).text.strip().replace(".", "")
            valid_colors = ["화이트", "블랙", "핑크", "블루", "그린", "옐로우", "레드", "그레이", "카키", "베이지", "퍼플", "브라운", "오렌지", "네이비", "와인", "우드", "투명", "실버", "골드", "차콜", "아이보리", "소라", "민트"]
            for vc in valid_colors:
                if vc in res: return vc
    except: pass
    return "혼합색상" 

def analyze_with_ai(api_key, raw_title, raw_text):
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        model = genai.GenerativeModel(next((m for m in models if '1.5-flash' in m), models[0]), generation_config={"response_mime_type": "application/json"})
        prompt = f"""원본 상품명: '{raw_title}'
        상품 원본 데이터 (이 안에서 소재/재질 정보를 찾아 한국어로 번역해. 정보가 없으면 '상세페이지 참조'라고 써): 
        '''{raw_text[:3000]}'''
        You must respond ONLY in valid JSON format exactly like this:
        {{"title": "제안명(브랜드명 제외, 핵심 4단어 이하)", "tags": "해시태그(#) 절대 없이 오직 단어만 쉼표(,)로 구분해서 10개 작성", "material": "한국어 번역된 소재", "alt_text": "시각장애인용 100자 요약", "season": "봄/여름/가을/겨울/사계절 중 택1"}}"""
        res = model.generate_content(prompt).text
        return json.loads(res.replace("```json", "").replace("```", "").strip()), None
    except Exception as e: return None, f"AI 가동 에러: {e}"