import pandas as pd
import re
import os
from module_api import get_color_from_image_ai

def get_clean_filename(brand, title, opt):
    # 이미지 파일명 띄어쓰기 유지, 혼합색상 및 특수기호 완벽 제거
    opt = str(opt).replace("혼합색상", "").replace("단일색상", "").replace("혼합", "").replace(",", "").strip()
    raw = f"{brand} {title} {opt}".strip()
    clean = re.sub(r'[\u4e00-\u9fff]', '', raw)
    clean = re.sub(r'[_\\/*?:"<>|,]', '', clean)
    return re.sub(r'\s+', ' ', clean).strip()

def find_target_txt(start_path):
    try:
        for f in os.listdir(start_path):
            if f.endswith("_URL.txt") or f.endswith(".txt"): return os.path.join(start_path, f), start_path
    except Exception as e: pass
    return None, None 

def extract_excel_columns(excel_path):
    try:
        xl = pd.ExcelFile(excel_path)
        for sheet in xl.sheet_names:
            df_temp = pd.read_excel(excel_path, sheet_name=sheet, header=None, nrows=10)
            if len(df_temp) > 5:
                row_5_str = " ".join([str(val) for val in df_temp.iloc[4].values])
                if "상품명" in row_5_str and "카테고리" in row_5_str:
                    return df_temp.iloc[4].tolist(), df_temp.iloc[5].tolist(), sheet 
    except Exception as e: pass
    return [], [], None

def clean_option_name(raw_opt, current_api_key=None, img_url=None):
    opt_str = str(raw_opt)
    
    # 1. 쉼표 제거 및 크롬 번역 오류 교정 ("남" -> "M", "엑스에스" -> "XS")
    opt_str = opt_str.replace(',', ' ').replace('，', ' ') 
    size_reverse_dict = {
        "엑스에스": "XS", "에스라지": "XL", "엑스라지": "XL", "투엑스라지": "2XL", "쓰리엑스라지": "3XL",
        "포엑스라지": "4XL", "파이브엑스라지": "5XL", 
        "에스": "S", "엠": "M", "엘": "L", "프리": "FREE", "난": "", "남": "M"
    }
    for kr_size, en_size in size_reverse_dict.items():
        opt_str = opt_str.replace(kr_size, en_size)

    ch_to_kr = {
        "白色": "화이트", "黑色": "블랙", "粉色": "핑크", "蓝色": "블루", "绿色": "그린", "黄色": "옐로우", "红色": "레드", 
        "灰色": "그레이", "卡其": "카키", "杏色": "베이지", "紫色": "퍼플", "棕色": "브라운", "橙色": "오렌지", 
        "彩色": "혼합색상", "酒红": "와인", "藏青": "네이비", "浅蓝": "라이트블루", "深蓝": "다크블루", 
        "米色": "아이보리", "驼色": "카멜", "墨绿": "다크그린", "军绿": "카키그린", "姜黄": "머스타드", 
        "砖红": "브릭레드", "香芋": "라벤더", "青色": "청록", "银色": "실버", "金色": "골드", "透明": "투명", 
        "木色": "우드", "原木": "우드", "咖色": "모카", "咖啡": "모카", "深灰": "다크그레이", "浅灰": "라이트그레이", 
        "玫瑰": "로즈", "宝蓝": "네이비", "豆沙": "인디핑크", "香槟": "샴페인", "荧光": "형광", "均码": "FREE"
        # [수술] 스트라이프, 체크무늬 살려두던 매핑 삭제!
    }
    for ch, kr in ch_to_kr.items(): opt_str = opt_str.replace(ch, kr)

    # 2. 진짜 사이즈를 '안전가옥'으로 대피시키기
    size = ""
    dim_pattern = r'(\d+(?:\.\d+)?(?:\s*[*xX/]\s*\d+(?:\.\d+)?)+(?:\s*[cC][mM])?|\d+(?:\.\d+)?\s*[cC][mM]|\d{2,3}\s*\([A-Za-z]+\))'
    dim_match = re.search(dim_pattern, opt_str)
    if dim_match:
        size_candidate = dim_match.group(1).strip()
        size = size_candidate
        opt_str = opt_str.replace(size_candidate, ' ')
    
    if not size:
        # XS 포함 사이즈 추출
        size_match = re.search(r'\b(XS|S|M|L|XL|2XL|3XL|4XL|5XL|FREE|소형|중형|대형|특대형)\b', opt_str, re.IGNORECASE)
        if size_match:
            size = size_match.group(1).upper()
            opt_str = re.sub(r'\b' + size + r'\b', ' ', opt_str, flags=re.IGNORECASE)

    # 3. 괄호 안에 '숫자'가 있는 경우만 통째로 도려내기 (예: (100-115) 삭제)
    opt_str = re.sub(r'\([^)]*\d[^)]*\)', ' ', opt_str)
    opt_str = re.sub(r'\[[^\]]*\d[^\]]*\]', ' ', opt_str)
    opt_str = re.sub(r'\{[^}]*\d[^}]*\}', ' ', opt_str)
    opt_str = re.sub(r'（[^）]*\d[^）]*）', ' ', opt_str)
    
    # 안에 글자(색상)만 들어있어서 살아남은 괄호들은 껍데기만 벗겨내서 내용물 보호
    opt_str = re.sub(r'[\[\(\{（\]\}\)）]', ' ', opt_str)

    # 4. 의류 영문 사이즈가 대피소에 있다면, 남은 옵션명의 숫자는 모두 쓰레기이므로 삭제
    if size and re.match(r'^(XS|S|M|L|XL|2XL|3XL|4XL|5XL|FREE)$', size, re.IGNORECASE):
        opt_str = re.sub(r'\d+', ' ', opt_str)

    # 5. [수술 핵심] 노이즈 단어 분쇄기에 무늬 관련 단어 전격 추가!
    noise_words = ["款", "型", "版", "色", "风", "男女公用", "套装", "升级", "正품", "同款", "이미지", "색상", "条纹", "格子", "줄무늬", "스트라이프", "체크무늬", "체크"]
    for nw in noise_words: opt_str = re.sub(r'(?i)' + re.escape(nw), ' ', opt_str)

    # 6. 만능 특수기호 분쇄기 (한글, 영문, 숫자, 공백 제외 모두 삭제)
    opt_str = re.sub(r'[^가-힣a-zA-Z0-9\s]', ' ', opt_str)
    opt_str = re.sub(r'\s+', ' ', opt_str).strip()

    # 7. 깎여나간 '혼합'을 다시 '혼합색상'으로 완벽 복원!
    if opt_str == "혼합" or opt_str == "":
        opt_str = "혼합색상"

    valid_color_keywords = ["화이트", "블랙", "핑크", "블루", "그린", "옐로우", "레드", "그레이", "카키", "베이지", "퍼플", "브라운", "오렌지", "네이비", "와인", "우드", "투명", "실버", "골드", "차콜", "아이보리", "소라", "민트", "혼합색상", "오로라", "멀티"]
    has_color = any(c in opt_str for c in valid_color_keywords)
    
    if not has_color and opt_str != "혼합색상":
        if current_api_key and img_url: 
            ai_color = get_color_from_image_ai(current_api_key, img_url)
            has_valid_ai = any(k in ai_color for k in valid_color_keywords)
            if not has_valid_ai or "이미지" in ai_color:
                opt_str = "혼합색상"
            else:
                opt_str = ai_color
        else: opt_str = "혼합색상" 

    if not opt_str: opt_str = "혼합색상"
    
    # 8. 대피소에 있던 사이즈를 다시 안전하게 결합
    if size: return f"{opt_str} {size}".strip()
    return opt_str

def split_color_size(opt_name):
    parts = opt_name.split(" ")
    if len(parts) > 1:
        size_part = parts[-1]
        # XS 추가
        if re.search(r'\d', size_part) or size_part.upper() in ["XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL", "FREE", "소형", "중형", "대형", "특대형"]:
            return " ".join(parts[:-1]), size_part
    if len(parts) == 1:
        if re.search(r'\d', parts[0]) or parts[0].upper() in ["XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL", "FREE", "소형", "중형", "대형", "특대형"]:
            return "혼합색상", parts[0]
    return opt_name, "상세페이지 참조"

def optimize_profit_margin(row, target_profit):
    cost = row['원가(원)']
    initial_supply = cost + target_profit
    min_coupang = initial_supply / 0.595 
    base_1000 = (int(min_coupang) // 1000) * 1000
    candidate = base_1000 + 800
    if candidate < min_coupang: candidate += 1000
    coupang_price = candidate
    final_supply = int(coupang_price * 0.595) 
    my_margin = final_supply - cost
    coupang_margin_pct = round((coupang_price - final_supply) / coupang_price * 100, 2)
    retail_price = ((int(coupang_price * 1.7) // 100) * 100)
    return pd.Series([final_supply, my_margin, coupang_price, coupang_margin_pct, retail_price])

def get_excel_mapped_value(c_raw, req_raw, d, sku, base_fname, brand_name, suggested_name, final_tags, alt_text, season, pack_weight, pack_size, custom_category=""):
    c = str(c_raw).strip().replace('\n', '') 
    req = str(req_raw).strip()
    
    c_color, c_size = split_color_size(sku['옵션명'])
    # 상품명 구성 시 혼합색상, 혼합, 쉼표 완전 투명화
    display_opt = sku['옵션명'].replace("혼합색상", "").replace("단일색상", "").replace("혼합", "").replace(",", "").strip()
    display_opt = re.sub(r'\s+', ' ', display_opt)
    cat_val = custom_category if custom_category else d.get('category', '')
    
    val = ""
    if "카테고리" in c: val = cat_val
    elif "상품명" in c and "영문" not in c: val = f"{brand_name} {suggested_name} {display_opt}".strip()
    elif "공급가" in c: val = sku.get('최종 납품가(원)', '')
    elif "쿠팡 판매가" in c or "쿠팡판매가" in c: val = sku.get('쿠팡판매가(원)', '')
    elif "권장소비자" in c or "공식 판매처 가격" in c or "공식판매처" in c: val = sku.get('권장소비자가(원)', '')
    elif "대표이미지" in c: val = f"{base_fname}.jpg"
    elif "추가이미지" in c: val = "" 
    elif "상세이미지" in c: val = f"{base_fname}detail.jpg"
    elif "필수 표시사항" in c or "필수표시사항" in c: val = f"{base_fname}label.jpg"
    elif "사이즈표" in c or "사이즈차트" in c: val = f"{base_fname}size.jpg"
    
    elif "색상" in c or "컬러" in c: val = c_color if c_color else "상세페이지 참조"
    elif any(kw in c for kw in ["사이즈", "크기", "치수"]) and "포장" not in c: 
        val = c_size if (c_size and c_size != "FREE") else "상세페이지 참조"
        
    elif "모델명" in c: val = suggested_name
    elif "바코드" in c: val = "바코드 없음(쿠팡 바코드 생성 요청)"
    elif "검색태그" in c: val = final_tags
    elif "대체 텍스트" in c or "대체텍스트" in c: val = alt_text
    elif "브랜드" in c: val = brand_name
    elif "제조자" in c or "수입자" in c: val = brand_name
    elif "제조사" in c: val = f"{brand_name} 협력사"
    elif "수량" == c: val = "1개"
    elif "포함 구성 요소" in c or "포함구성요소" in c: val = "해당없음"
    elif "과세여부" in c: val = "과세"
    elif "거래타입" in c: val = "기타 도소매업자"
    elif "수입여부" in c: val = "수입상품"
    elif "SKU 수량" in c: val = "100"
    elif "유통기" in c: val = "0"
    elif "취급주의" in c: val = "해당사항없음"
    elif "포장 무게" in c or "포장무게" in c: val = pack_weight
    elif "포장 사이즈" in c or "포장사이즈" in c: val = pack_size
    elif "출시 연도" in c or "출시연도" in c: val = "2026"
    elif "계절" in c: val = season
    elif "제조국" in c: val = "중국"
    elif "전화번호" in c: val = "고객센터 070-4128-6398"
    elif "품질보증" in c: val = "소비자분쟁해결기준에 의거 보상"
    elif "인증" in c or "신고번호" in c: val = "해당사항없음"
    elif "고시명" in c: val = ""  
    elif "행어 입고" in c or "행어입고" in c: val = "N"
    
    elif "허가사항" in c or "주의사항" in c: val = ""
    elif "종류" in c: val = ""
    elif "소재" in c or "재질" in c: val = d['attributes'].get('소재', '')
    
    # 6행이 "선택"일 경우 겹치는 오류 방지를 위해 무조건 빈칸 처리 (필수 항목은 제외)
    core_fields = ["카테고리", "상품명", "공급가", "판매가", "권장소비자", "판매처", "이미지", "표시사항", "사이즈표", "사이즈차트", "바코드", "검색태그", "HTML"]
    is_core = any(core in c for core in core_fields)
    if "선택" in req and not is_core:
        return ""

    # 필수 또는 조건부 필수일 때 값이 비어있으면 든든하게 막아줌
    if not val and ("필수" in req or "조건부" in req) and "고시명" not in c:
        return "상세페이지 참조"
    return val

def read_urls_from_file(folder_path):
    items = []
    try:
        for f in os.listdir(folder_path):
            if f.startswith('~$'): continue
            file_path = os.path.join(folder_path, f)
            if f.endswith('.txt') and 'url' in f.lower():
                with open(file_path, 'r', encoding='utf-8') as txt_file:
                    for l in txt_file.readlines():
                        l = l.strip()
                        if l.startswith('http'): items.append({"url": l, "category": "", "template": ""})
            elif f.endswith('.xlsx') and 'url' in f.lower():
                df = pd.read_excel(file_path, header=None)
                for _, row in df.iterrows():
                    url_val, cat_val, tpl_val = "", "", ""
                    for cell in row:
                        val = str(cell).strip()
                        if val == 'nan' or not val: continue
                        if val.startswith('http'): url_val = val
                        elif '>' in val or '(' in val: cat_val = val
                        elif '견적서' in val or '.xlsx' in val.lower():
                            tpl_val = val if val.lower().endswith('.xlsx') else val + '.xlsx'
                    if url_val: items.append({"url": url_val, "category": cat_val, "template": tpl_val})
    except Exception as e: pass
        
    unique_items = []
    seen = set()
    for item in items:
        if item['url'] not in seen:
            seen.add(item['url'])
            unique_items.append(item)
    return unique_items

def find_excel_template(folder_path, target_category=None):
    templates = []
    try:
        for f in os.listdir(folder_path):
            if f.endswith(".xlsx") and not f.endswith("_제출.xlsx") and not f.startswith("~$") and 'url' not in f.lower():
                templates.append(os.path.join(folder_path, f))
    except: pass
    
    if not templates: return None
    if len(templates) == 1: return templates[0]
    
    if target_category:
        cat_code_match = re.search(r'\((\d+)\)', target_category)
        cat_code = cat_code_match.group(1) if cat_code_match else None
        if cat_code:
            for t in templates:
                if cat_code in t: return t
        cat_words = [w.strip() for w in target_category.replace('>', '/').split('/') if w.strip()]
        for t in templates:
            for w in cat_words[-2:]:
                if w in t: return t
    return templates[0]

def get_all_valid_folders(start_path):
    valid_folders = []
    try:
        for root, dirs, files in os.walk(start_path):
            if "_최종결과물" in root: continue 
            for f in files:
                if f.endswith("_URL.txt") or f.endswith(".txt"): 
                    if root not in valid_folders: valid_folders.append(root)
    except Exception as e: pass
    return sorted(valid_folders) 

def fix_path(raw_path):
    p = str(raw_path).strip(' "\'')
    return os.path.dirname(p) if os.path.isfile(p) else p

def parse_1688_text(raw_text, current_api_key):
    data = {"sku_list": [], "product_title": "", "attributes": {}, "main_imgs": [], "sku_imgs": [], "detail_imgs": [], "category": ""}
    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    if lines and not lines[0].startswith("제품 제목") and not lines[0].startswith('"http'):
        data["category"] = lines[0].replace("카테고리:", "").strip()
        
    try: data["product_title"] = re.search(r'제품 제목:\n(.*?)\n', raw_text).group(1).strip()
    except: pass
    
    data["attributes"]["소재"] = "상세페이지 참조" 
    data["attributes"]["사이즈"] = "프리사이즈"
    
    try: 
        weight_match = re.search(r'(?:重量|중량|무게|weight).*?([\d\.]+)\s*(kg|g|KG|G)?', raw_text)
        if weight_match:
            val = float(weight_match.group(1))
            unit = weight_match.group(2)
            if unit and unit.lower() == 'kg': val *= 1000
            elif val < 10: val *= 1000 
            data["attributes"]["무게"] = str(int(val))
        else: data["attributes"]["무게"] = "500"
    except: data["attributes"]["무게"] = "500"

    def extract_links(start, end=None):
        try:
            sec = raw_text.split(start)[1]
            if end: sec = sec.split(end)[0]
            return [l.strip().replace('"', '') for l in sec.split('\n') if l.strip().startswith('http')]
        except: return []

    data["main_imgs"] = extract_links("메인 이미지:", "동영상:")
    data["sku_imgs"] = extract_links("SKU 속성 이미지:", "설명 이미지:")
    data["detail_imgs"] = extract_links("설명 이미지:")
    
    fallback_img = data["main_imgs"][0] if data["main_imgs"] else ""
    for line in raw_text.split('\n'):
        if line.startswith('"http') and '\t' in line:
            parts = line.split('\t')
            if len(parts) >= 4:
                img_url = parts[0].strip('"')
                if not img_url: img_url = fallback_img 
                raw_opt_name = parts[1].strip('"')
                clean_opt = clean_option_name(raw_opt_name, current_api_key, img_url) 
                price_str = re.sub(r'[^\d.]', '', parts[3])
                data["sku_list"].append({"옵션명": clean_opt, "위안화": float(price_str) if price_str else 0.0, "이미지": img_url})
    return data