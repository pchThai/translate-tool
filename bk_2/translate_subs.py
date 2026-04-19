import os
import time
import argparse
from collections import deque
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Log, Static
from textual import work

# ==========================================
# 1. DANH SÁCH API KEYS (TỪ NHIỀU GMAIL KHÁC NHAU)
# ==========================================
API_KEYS = [
    "AIzaSyCEs_tbpa-_FyqU3yPQKbHTHuO2CLzn9f8", # Futoshi
    "AIzaSyCfvmAAtudh4QYkl7qOGjX6m-9NYAvzS-g", # Detu
    "AIzaSyBd9l3RvvrNV6e4r3ISGkztg8ogk_lVj1Q", # pch
    "AIzaSyDLWMWDno-uOlfAMwsC387a3O2bQM2M-N0", # tamano
    "AIzaSyB9xWxvaVWAnzN0cQ4-1mKnI1IgbX0jIww", # Arisu
    "AIzaSyAr5Pbs8Vbr5gEDhmTtpjaPkl1aVuvvmkk"  # Yuki
]

TOPIC = "Spring Security 6, JWT, OAuth2, Microservices"
GLOSSARY = "Filter Chain: Chuỗi lọc, Authentication: Xác thực, Authorization: Phân quyền, Principal: Đối tượng thực thể"

# ==========================================
# 2. LOGIC KIỂM TOÁN (DEEP AUDIT)
# ==========================================
def is_valid_translation(file_path):
    if not os.path.exists(file_path): return False
    if os.path.getsize(file_path) < 100: return False
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            if "-->" not in f.read(): return False
    except: return False
    return True

# ==========================================
# 3. QUẢN LÝ BOT API VÀ XOAY VÒNG KEY
# ==========================================
class TranslatorBot:
    def __init__(self, keys, log_fn):
        self.keys = keys
        self.current_key_index = 0
        self.model = None
        self.failed_cycles = 0
        self.max_cycles = 5
        self.log_fn = log_fn  
        self.setup_model()

    def setup_model(self):
        current_key = self.keys[self.current_key_index]
        genai.configure(api_key=current_key)
        try:
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods and 'flash' in m.name.lower()]
            model_name = models[0] if models else 'gemini-1.5-flash'
        except:
            model_name = 'gemini-1.5-flash'
            
        self.log_fn(f"[!] Dùng Key #{self.current_key_index + 1} | Model: {model_name}")
        self.model = genai.GenerativeModel(model_name)

    def rotate_key(self):
        self.current_key_index += 1
        if self.current_key_index >= len(self.keys):
            self.current_key_index = 0
            self.failed_cycles += 1
            self.log_fn(f"\n[♻️] Quay hết 1 vòng. Vòng thất bại: {self.failed_cycles}/{self.max_cycles}")
            time.sleep(15) # Nghỉ 15s cho server xả án phạt
            
        if self.failed_cycles < self.max_cycles:
            self.setup_model()
            return True
        return False

    def mark_success(self):
        self.failed_cycles = 0

# ==========================================
# 4. TRACKER (THỐNG KÊ QUOTA & RPM)
# ==========================================
class StatsTracker:
    def __init__(self):
        self.request_timestamps = deque()
        self.total_success = 0
        self.total_failed = 0

    def add_request(self, success=True):
        now = time.time()
        self.request_timestamps.append(now)
        if success:
            self.total_success += 1
        else:
            self.total_failed += 1
        self.clean_old()

    def clean_old(self):
        now = time.time()
        while self.request_timestamps and now - self.request_timestamps[0] > 60:
            self.request_timestamps.popleft()

    def get_rpm(self):
        self.clean_old()
        return len(self.request_timestamps)
        
    def generate_report(self):
        rpm = self.get_rpm()
        rpm_color = "[red]" if rpm >= 12 else "[green]"
        return f"🔥 Tốc độ (RPM): {rpm_color}{rpm}/15[/] req/min  |  ✅ Hoàn tất: {self.total_success}  |  ❌ Lỗi/Thử lại: {self.total_failed}"

# ==========================================
# 5. GIAO DIỆN TUI (TEXTUAL)
# ==========================================
class TranslatorTUI(App):
    CSS = """
    Screen {
        layout: grid;
        grid-size: 1 3;
        grid-rows: 3 2fr 1fr;
    }
    #stats_panel {
        border: solid cyan;
        content-align: center middle;
        text-style: bold;
        color: lime;
    }
    DataTable {
        border: solid green;
        height: 100%;
    }
    Log {
        border: solid yellow;
        height: 100%;
        background: $surface;
    }
    """

    BINDINGS = [
        ("s", "start_translation", "Bắt đầu Dịch"),
        ("q", "quit", "Thoát")
    ]

    def __init__(self, target_dir: str):
        super().__init__()
        self.target_dir = target_dir
        self.missing_files = [] 
        self.total_files = 0
        self.done_files = 0
        self.col_keys = [] 

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("Đang khởi tạo thống kê...", id="stats_panel")
        yield DataTable(id="file_table")
        yield Log(id="sys_log")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        self.col_keys = table.add_columns("STT", "Tên File", "Trạng Thái", "API Key", "Loại Lỗi")
        
        sys_log = self.query_one(Log)
        sys_log.write_line(f"[*] Đang quét (Deep Audit): {self.target_dir}...")

        row_idx = 0
        for root, _, files in sorted(os.walk(self.target_dir)):
            for f in sorted(files):
                if f.endswith((".vtt", ".srt")) and "_vi." not in f:
                    self.total_files += 1
                    full_path = os.path.join(root, f)
                    ext = f.rsplit('.', 1)[1]
                    vi_file = f.rsplit('.', 1)[0] + '_vi.' + ext
                    vi_full_path = os.path.join(root, vi_file)
                    
                    if is_valid_translation(vi_full_path):
                        self.done_files += 1
                        # THÊM DẤU TÍCH XANH CHO FILE ĐÃ XONG TỪ TRƯỚC
                        table.add_row(str(row_idx+1), f"✅ {f}", "✅ Đã xong", "Đã có", "-")
                    else:
                        row_key = table.add_row(str(row_idx+1), f, "⏳ Chờ dịch", "-", "-")
                        self.missing_files.append({"path": full_path, "row_key": row_key, "filename": f})
                    
                    row_idx += 1

        sys_log.write_line(f"📊 KIỂM TOÁN: Tổng {self.total_files} | Xong {self.done_files} | Cần dịch {len(self.missing_files)}")
        sys_log.write_line("[*] NHẤN PHÍM 'S' ĐỂ BẮT ĐẦU CHIẾN DỊCH!")

    @work(thread=True)
    def action_start_translation(self) -> None:
        sys_log = self.query_one(Log)
        table = self.query_one(DataTable)
        stats_panel = self.query_one("#stats_panel", Static)
        
        tracker = StatsTracker()

        def ui_log(msg): self.call_from_thread(sys_log.write_line, msg)
        def ui_update(row_key, col_idx, text): 
            self.call_from_thread(table.update_cell, row_key, self.col_keys[col_idx], text)
        def ui_update_stats(): 
            self.call_from_thread(stats_panel.update, tracker.generate_report())

        if not self.missing_files:
            ui_log("🎉 Không còn file nào sót! Bấm 'Q' để thoát.")
            return

        ui_log("🚀 Khởi động Translator Bot...")
        bot = TranslatorBot(API_KEYS, ui_log)
        ctx = ""

        ui_update_stats()

        for item in self.missing_files:
            file_path = item["path"]
            row_key = item["row_key"] 
            filename = item["filename"]

            ui_log(f"\n-> Đang xử lý: {filename}")
            ui_update(row_key, 2, "🔄 Đang dịch...") 
            ui_update(row_key, 4, "-") # Xóa cột lỗi cũ nếu có

            ext = file_path.rsplit('.', 1)[1]
            new_path = file_path.rsplit('.', 1)[0] + '_vi.' + ext
            
            while True:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    prompt = f"Dịch phụ đề sang tiếng Việt chuyên ngành IT. Ngữ cảnh: {TOPIC}. Thuật ngữ: {GLOSSARY}. Đoạn trước: {ctx[-300:]}. Giữ nguyên timestamp. Chỉ trả về nội dung dịch.\n\n{content}"
                    
                    # --- AUTO-BRAKE ---
                    while tracker.get_rpm() >= 14:
                        ui_log("   [!] RPM chạm 14. Tự động hãm phanh chờ 5s...")
                        time.sleep(5)
                        ui_update_stats()

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
                    
                    tracker.add_request(success=True)
                    ui_update_stats()

                    if not response.text: raise Exception("Empty Response")

                    text = response.text.strip().replace("```vtt", "").replace("```srt", "").replace("```", "").strip()
                    with open(new_path, 'w', encoding='utf-8') as f:
                        f.write(text)
                    
                    ui_log(f"   [OK] Đã lưu: {os.path.basename(new_path)}")
                    
                    # THÊM DẤU TÍCH XANH KHI DỊCH XONG
                    ui_update(row_key, 1, f"✅ {filename}")
                    ui_update(row_key, 2, "✅ Hoàn tất")
                    ui_update(row_key, 3, f"Key_{bot.current_key_index + 1}")
                    ui_update(row_key, 4, "-")
                    
                    bot.mark_success()
                    ctx = text
                    time.sleep(5) 
                    break 

                except Exception as e:
                    tracker.add_request(success=False)
                    ui_update_stats()
                    
                    err = str(e).lower()
                    
                    # ----------------------------------------------------
                    # PHÂN LOẠI LỖI ĐỂ TÌM RA NGUYÊN NHÂN "CHẾT KEY"
                    # ----------------------------------------------------
                    if "403" in err or "permission" in err or "api_key" in err:
                        error_type = "Lỗi 403 (Sai Key/Chưa bật API)"
                        ui_log(f"   [XXX] Key #{bot.current_key_index + 1} CHẾT HẲN: {error_type}")
                        ui_update(row_key, 2, "⚠️ Đổi Key")
                        ui_update(row_key, 4, "403 - Permission")
                        if not bot.rotate_key(): return
                        
                    elif "429" in err or "quota" in err:
                        error_type = "Lỗi 429 (Hết Quota hoặc bị chặn IP)"
                        ui_log(f"   [!] Key #{bot.current_key_index + 1} quá tải: {error_type}")
                        ui_update(row_key, 2, "⚠️ Đổi Key")
                        ui_update(row_key, 4, "429 - Quota/RPM")
                        if not bot.rotate_key(): 
                            ui_log("\n[XXX] TẤT CẢ KEY ĐÃ CẠN KIỆT. CHỜ 24H!")
                            ui_update(row_key, 2, "❌ Dừng")
                            return
                        time.sleep(5)
                        
                    elif "504" in err or "503" in err or "deadline" in err or "internal" in err:
                        error_type = "Lỗi 500+ (Google Server Lag)"
                        ui_log(f"   [!] {error_type}, chờ 10s...")
                        ui_update(row_key, 4, "50x - Server Lag")
                        time.sleep(10)
                        
                    else:
                        ui_log(f"   [X] Lỗi lạ, bỏ qua file: {e}")
                        ui_update(row_key, 2, "❌ Lỗi Lạ")
                        ui_update(row_key, 4, "Lỗi Script")
                        break

        ui_log("\n" + "="*50 + "\n✅ CHIẾN DỊCH HOÀN TẤT!")

# ==========================================
# KHỞI CHẠY
# ==========================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--dir", required=True, help="Đường dẫn đến khóa học")
    args = parser.parse_args()
    
    path = os.path.abspath(os.path.expanduser(args.dir))

    if not os.path.isdir(path):
        print(f"Lỗi: Thư mục '{path}' không tồn tại.")
        exit(1)

    app = TranslatorTUI(target_dir=path)
    app.run()