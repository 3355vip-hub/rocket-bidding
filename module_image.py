import os
import textwrap
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageChops
from rembg import remove
from module_api import download_img
from module_data import split_color_size

def get_font(size, is_bold=False):
    font_name = "malgunbd.ttf" if is_bold else "malgun.ttf"
    try: return ImageFont.truetype(f"C:/Windows/Fonts/{font_name}", size)
    except: return ImageFont.load_default()

def draw_center_text(draw, text, font, x, y, fill):
    try: text_w = draw.textlength(text, font=font)
    except: text_w = len(text) * (font.size * 0.5)
    draw.text((x - text_w/2, y), text, fill=fill, font=font)

def trim_and_crop_1_to_1(img):
    w, h = img.size
    if w == h: return img 
    max_side = max(w, h)
    canvas = Image.new("RGB", (max_side, max_side), "white")
    offset_x = (max_side - w) // 2
    offset_y = (max_side - h) // 2
    canvas.paste(img, (offset_x, offset_y))
    return canvas

def process_user_thumbnail(img):
    return trim_and_crop_1_to_1(img)

def create_studio_main_image(img):
    try:
        no_bg = remove(img) 
        bbox = no_bg.getbbox()
        if not bbox: return img 
        cropped = no_bg.crop(bbox)
        canvas_size = 800
        canvas = Image.new("RGB", (canvas_size, canvas_size), "white")
        target_size = int(canvas_size * 0.9)
        w, h = cropped.size
        ratio = min(target_size / w, target_size / h)
        new_w, new_h = int(w * ratio), int(h * ratio)
        resized_product = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)
        offset_x = (canvas_size - new_w) // 2
        offset_y = (canvas_size - new_h) // 2
        canvas.paste(resized_product, (offset_x, offset_y), resized_product)
        return canvas
    except: return img 

def create_dynamic_detail_page(full_title, option_name, material, size, origin, img_urls, brand_name="미화부장"):
    valid_imgs = []
    total_img_height = 0
    target_img_w = 700
    for url in img_urls: 
        if not url: continue
        if os.path.isfile(url): img = Image.open(url).convert("RGB")
        else: img = download_img(url)
        if img:
            ratio = target_img_w / img.width
            new_h = int(img.height * ratio)
            valid_imgs.append(img.resize((target_img_w, new_h), Image.Resampling.LANCZOS))
            total_img_height += new_h
            
    gap = 50
    total_gap_height = gap * (len(valid_imgs) - 1) if valid_imgs else 0
    top_margin = 250 
    bottom_margin = 500 
    total_canvas_height = top_margin + total_img_height + total_gap_height + bottom_margin
    
    canvas = Image.new('RGB', (760, total_canvas_height), 'white')
    draw = ImageDraw.Draw(canvas)
    
    draw_center_text(draw, full_title, get_font(32, True), 380, 80, "#111111") 
    draw.rectangle([280, 140, 480, 142], fill="#dddddd") 
    draw_center_text(draw, option_name, get_font(24, False), 380, 160, "#555555")
    
    current_y = top_margin
    for img in valid_imgs:
        canvas.paste(img, (30, current_y))
        current_y += img.height + gap
        
    current_y += 50 
    draw.rectangle([0, current_y, 760, current_y + 2], fill="#eeeeee")
    current_y += 50
    draw_center_text(draw, "상 품 정 보 표 시", get_font(28, True), 380, current_y, "#111111")
    current_y += 80
    
    info_list = [("상품명", full_title), ("옵션", option_name), ("소재", material), ("사이즈", size), ("제조국", origin), ("수입원", brand_name)]
    start_x = 100
    for key, value in info_list:
        draw.text((start_x, current_y), f"• {key}", fill="#666666", font=get_font(20, False))
        draw.text((start_x + 150, current_y), str(value), fill="#222222", font=get_font(20, False))
        current_y += 40
        
    current_y += 40
    notice = "※ 사이즈는 측정 방법과 위치에 따라 1~3cm 오차가 발생할 수 있습니다.\n※ 모니터 해상도에 따라 실제 제품과 색상 차이가 있을 수 있습니다."
    draw.text((start_x, current_y), notice, fill="#999999", font=get_font(18), spacing=10)
    return canvas

def create_perfect_korean_label_900x1200(full_item_name, size, material, importer, phone, save_path=None):
    img = Image.new('RGB', (900, 1200), color='white')
    draw = ImageDraw.Draw(img)
    try: font_title, font_body = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 48), ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 36)   
    except: font_title = font_body = ImageFont.load_default()
        
    start_x, current_y = 60, 80
    draw.text((start_x, current_y), "전기용품 및 생활안전관리법 표시", fill="black", font=font_title)
    current_y += 100
    
    wrapped_name = textwrap.fill(full_item_name, width=24) 
    draw.text((start_x, current_y), wrapped_name, fill="black", font=font_body, spacing=20)
    current_y += (len(wrapped_name.split('\n')) * 55) + 60
    
    lines = [f"사이즈: {size}", f"소재: {textwrap.fill(material, width=22)}", f"제조년월: {datetime.now().strftime('%Y년 %m월')}", "제조국: 중국", f"수입판매원:\n{textwrap.fill(importer, width=24)}", f"고객센터: {phone}"]
    for line in lines:
        draw.text((start_x, current_y), line, fill="black", font=font_body, spacing=15)
        current_y += (len(line.split('\n')) * 55) + 20

    if current_y < 1200: img = img.crop((0, 0, 900, 1200)) 
    else: img = img.resize((900, 1200), Image.Resampling.LANCZOS) 
        
    if save_path: img.save(save_path, format="JPEG", quality=100)
    return img

def create_smart_size_chart(sku_list, save_path=None):
    found_sizes = set()
    for sku in sku_list:
        _, size = split_color_size(sku['옵션명'])
        found_sizes.add(size.upper())
    
    # [수술 지점 1] 정렬 순서 맨 앞에 "XS" 추가
    standard_order = ["소형", "중형", "대형", "특대형", "XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL", "FREE"]
    sorted_sizes = [s for s in standard_order if s in found_sizes]
    if not sorted_sizes: sorted_sizes = list(found_sizes) or ["FREE"]

    # [수술 지점 2] XS 데이터 추가
    ref_data = {"XS": ("150-155", "35-40"), "S": ("155-160", "40-50"), "M": ("160-165", "50-60"), "L": ("165-170", "60-65"), "XL": ("170-175", "65-70"), "2XL": ("175-180", "70-75"), "3XL": ("180-185", "75-80"), "4XL": ("185-190", "80-85"), "5XL": ("185-190", "85-90"), "FREE": ("155-165", "40-60"), "소형": ("상세페이지 참조", "상세페이지 참조"), "중형": ("상세페이지 참조", "상세페이지 참조"), "대형": ("상세페이지 참조", "상세페이지 참조"), "특대형": ("상세페이지 참조", "상세페이지 참조")}
    
    headers = ["사이즈", "권장신장(cm)", "권장체중(kg)"]
    rows = [[s, ref_data.get(s, ("상세페이지 참조", "상세페이지 참조"))[0], ref_data.get(s, ("상세페이지 참조", "상세페이지 참조"))[1]] for s in sorted_sizes]

    row_h, start_y = 60, 100
    img = Image.new('RGB', (800, start_y + (len(rows) + 1) * row_h + 100), color='white')
    draw = ImageDraw.Draw(img)
    
    try: font_title, font_td = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 32), ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 24)
    except: font_title = font_td = ImageFont.load_default()

    draw.text((40, 40), "■ 상품 사이즈 안내", fill="black", font=font_title)
    col_w, start_x = 720 / len(headers), 40
    
    def draw_cell(d, text, x, y, w, h, is_header=False):
        d.rectangle([x, y, x+w, y+h], fill="#f4f4f4" if is_header else "#ffffff", outline="#cccccc", width=1)
        try: text_w = d.textlength(str(text), font=font_td)
        except: text_w = 40
        d.text((x + (w - text_w) / 2, y + (h - 26) / 2), str(text), fill="#222222", font=font_td)

    for i, h_text in enumerate(headers): draw_cell(draw, h_text, start_x + i * col_w, start_y, col_w, row_h, True)
    for r_idx, row in enumerate(rows):
        y = start_y + (r_idx + 1) * row_h
        for c_idx, cell_val in enumerate(row): draw_cell(draw, cell_val, start_x + c_idx * col_w, y, col_w, row_h, False)
            
    draw.text((40, y + row_h + 30), "※ 측정 방법과 위치에 따라 1~3cm 오차가 발생할 수 있습니다.", fill="#777777", font=font_td)
    if save_path: img.save(save_path, format="JPEG", quality=95)
    return img

def get_local_images(folder_path, keyword):
    try:
        files = [f for f in os.listdir(folder_path) if f.startswith(keyword) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
        files.sort()
        return [os.path.join(folder_path, f) for f in files]
    except: return []

def get_final_detail_urls(folder_path, d, sku, strategy_str):
    if not folder_path: 
        return d['detail_imgs'] if ("옵션 2" in strategy_str and d['detail_imgs']) else ([sku['이미지']] + d['main_imgs'])
        
    local_details = get_local_images(folder_path, "설명 이미지")
    local_mains = get_local_images(folder_path, "메인 이미지")
    detail_urls = local_details if local_details else d['detail_imgs']
    main_urls = local_mains if local_mains else d['main_imgs']
    
    if "옵션 2" in strategy_str: return detail_urls if detail_urls else ([sku['이미지']] + main_urls)
    else: return [sku['이미지']] + main_urls