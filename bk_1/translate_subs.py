import os
import time
import argparse
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# ==========================================
# 1. DANH SÁCH API KEYS (XOAY VÒNG KHI HẾT QUOTA)
# ==========================================
API_KEYS = [
    "AIzaSyCEs_tbpa-_FyqU3yPQKbHTHuO2CLzn9f8", #Futoshi
    "AIzaSyCfvmAAtudh4QYkl7qOGjX6m-9NYAvzS-g", #Detu
    "AIzaSyBd9l3RvvrNV6e4r3ISGkztg8ogk_lVj1Q", #pch
    "AIzaSyDLWMWDno-uOlfAMwsC387a3O2bQM2M-N0", # tamano
    "AIzaSyB9xWxvaVWAnzN0cQ4-1mKnI1IgbX0jIww", # Arisu
    "AIzaSyAr5Pbs8Vbr5gEDhmTtpjaPkl1aVuvvmkk" # Yuki
]

class TranslatorBot:
    def __init__(self, keys):
        self.keys = keys
        self.current_key_index = 0
        self.model = None
        self.setup_model()

    def setup_model(self):
        current_key = self.keys[self.current_key_index]
        genai.configure(api_key=current_key)
        try:
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods and 'flash' in m.name.lower()]
            model_name = models[0] if models else 'gemini-1.5-flash'
        except:
            model_name = 'gemini-1.5-flash'
        print(f"\n[!] Chuyển sang Key #{self.current_key_index + 1} | Model: {model_name}")
        self.model = genai.GenerativeModel(model_name)

    def rotate_key(self):
        if self.current_key_index < len(self.keys) - 1:
            self.current_key_index += 1
            self.setup_model()
            return True
        return False

# ==========================================
# 2. CẤU HÌNH NGỮ CẢNH CHUYÊN NGÀNH
# ==========================================
TOPIC = "Spring Security 6, JWT, OAuth2, Microservices"
GLOSSARY = "Filter Chain: Chuỗi lọc, Authentication: Xác thực, Authorization: Phân quyền, Principal: Đối tượng thực thể"

def is_valid_translation(file_path):
    """Deep Audit: Kiểm tra xem file dịch có thực sự 'chất lượng' không"""
    if not os.path.exists(file_path):
        return False
    # 1. Check dung lượng (phải > 100 bytes cho chắc)
    if os.path.getsize(file_path) < 100:
        return False
    # 2. Check nội dung (phải có ký hiệu timestamp đặc trưng của phụ đề)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if "-->" not in content:
                return False
    except:
        return False
    return True

def translate_file(bot, file_path, ctx=""):
    ext = file_path.rsplit('.', 1)[1]
    new_path = file_path.rsplit('.', 1)[0] + '_vi.' + ext
    
    filename = os.path.basename(file_path)
    print(f"-> Đang dịch: {filename}")
    
    while True:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            prompt = f"Dịch phụ đề sang tiếng Việt chuyên ngành IT. Ngữ cảnh: {TOPIC}. Thuật ngữ: {GLOSSARY}. Đoạn trước: {ctx[-300:]}. Giữ nguyên timestamp. Chỉ trả về nội dung dịch.\n\n{content}"
            
            response = bot.model.generate_content(
                prompt, 
                request_options={"timeout": 600},
                safety_settings={cat: HarmBlockThreshold.BLOCK_NONE for cat in [
                    HarmCategory.HARM_CATEGORY_HARASSMENT, 
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH, 
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, 
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT
                ]}
            )
            
            if not response.text: raise Exception("Empty Response")

            text = response.text.strip().replace("```vtt", "").replace("```srt", "").replace("```", "").strip()
            with open(new_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            print(f"   [OK] Đã lưu: {os.path.basename(new_path)}")
            return text

        except Exception as e:
            err = str(e).lower()
            if "429" in err or "quota" in err:
                print(f"   [!] Key #{bot.current_key_index + 1} hết hạn. Đang đổi Key...")
                if bot.rotate_key(): 
                    time.sleep(2)
                    continue
                else: 
                    print("[XXX] TẤT CẢ KEY ĐÃ HẾT HẠN TRONG HÔM NAY."); exit()
            elif "504" in err or "503" in err or "deadline" in err:
                print(f"   [!] Lỗi server ({e}), chờ 10s rồi thử lại...")
                time.sleep(10)
                continue
            else:
                print(f"   [X] Lỗi, bỏ qua file {filename}: {e}")
                return ctx

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--dir", required=True)
    args = parser.parse_args()
    path = os.path.abspath(os.path.expanduser(args.dir))

    if not os.path.isdir(path):
        print(f"Lỗi: Thư mục '{path}' không tồn tại.")
        return

    # --- GIAI ĐOẠN 1: DEEP AUDIT (KIỂM TOÁN) ---
    all_files = []
    missing_files = []
    
    for root, _, files in os.walk(path):
        for f in files:
            if f.endswith((".vtt", ".srt")) and "_vi." not in f:
                full_path = os.path.join(root, f)
                all_files.append(full_path)
                
                ext = f.rsplit('.', 1)[1]
                vi_file = f.rsplit('.', 1)[0] + '_vi.' + ext
                vi_full_path = os.path.join(root, vi_file)
                
                # Check Deep Audit: Xem file _vi có tồn tại, đủ dung lượng và đúng format không
                if not is_valid_translation(vi_full_path):
                    missing_files.append(full_path)

    total = len(all_files)
    done = total - len(missing_files)
    
    print("="*50)
    print(f"📊 BÁO CÁO KIỂM TOÁN THƯ MỤC:")
    print(f"   - Tổng số file gốc tìm thấy: {total}")
    print(f"   - Đã dịch thành công: {done}")
    print(f"   - Còn sót/Lỗi cần dịch lại: {len(missing_files)}")
    print("="*50)

    if not missing_files:
        print("🎉 Tuyệt vời! Không còn file nào bị sót. Nghỉ ngơi thôi đại ca!")
        return

    # --- GIAI ĐOẠN 2: SWEEP (DỊCH NỐT) ---
    print(f"🚀 Bắt đầu dịch {len(missing_files)} file còn lại...")
    bot = TranslatorBot(API_KEYS)
    ctx = ""
    
    for i, file_path in enumerate(sorted(missing_files)):
        print(f"\n[{i+1}/{len(missing_files)}]", end=" ")
        ctx = translate_file(bot, file_path, ctx)
        time.sleep(7) # Tránh lỗi 429 RPM

    print("\n" + "="*50 + "\n✅ ĐÃ QUÉT SẠCH VÀ DỊCH XONG TOÀN BỘ!")

if __name__ == "__main__":
    main()