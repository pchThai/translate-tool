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
# 1. DANH SÁCH API KEYS
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
# 3. QUẢN LÝ BOT API
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
            
        self.log_fn(f"[!] Kích hoạt Key #{self.current_key_index + 1}")
        self.model = genai.GenerativeModel(model_name)

    def rotate_key(self):
        self.current_key_index += 1
        if self.current_key_index >= len(self.keys):
            self.current_key_index = 0
            self.failed_cycles += 1
            self.log_fn(f"\n[♻️] Quay hết 1 vòng các Key. Vòng lỗi: {self.failed_cycles}/{self.max_cycles}")
            time.sleep(10)
            
        if self.failed_cycles < self.max_cycles:
            self.setup_model()
            return True
        return False

# ==========================================
# 4. TRACKER (THỐNG KÊ CHI TIẾT)
# ==========================================
class StatsTracker:
    def __init__(self):
        self.all_attempts = deque() # Lưu mọi lần bấm nút gửi
        self.total_success = 0
        self.total_failed = 0

    def log_attempt(self):
        self.all_attempts.append(time.time())
        self.clean_old()

    def clean_old(self):
        now = time.time()
        while self.all_attempts and now - self.all_attempts[0] > 60:
            self.all_attempts.popleft()

    def get_rpm(self):
        self.clean_old()
        return len(self.all_attempts)
        
    def generate_report(self):
        rpm = self.get_rpm()
        rpm_color = "[bold red]" if rpm >= 12 else "[bold green]"
        return f"📊 [cyan]Hệ thống:[/] RPM thực tế: {rpm_color}{rpm}/15[/]  |  ✅ Xong: [green]{self.total_success}[/]  |  ❌ Lỗi: [red]{self.total_failed}[/]"

# ==========================================
# 5. GIAO DIỆN TUI (TEXTUAL)
# ==========================================
class TranslatorTUI(App):
    CSS = """
    Screen {
        layout: grid;
        grid-size: 4 3;
        grid-rows: 3 2fr 1fr;
    }
    #stats_panel {
        column-span: 4;
        border: double cyan;
        content-align: center middle;
        background: $surface;
    }
    #file_table {
        column-span: 3;
        border: solid green;
    }
    #key_table {
        column-span: 1;
        border: solid magenta;
    }
    #sys_log {
        column-span: 4;
        border: solid yellow;
    }
    """

    BINDINGS = [("s", "start_translation", "Bắt đầu"), ("q", "quit", "Thoát")]

    def __init__(self, target_dir: str):
        super().__init__()
        self.target_dir = target_dir
        self.missing_files = [] 
        self.key_attempts = [0] * len(API_KEYS)
        self.key_success = [0] * len(API_KEYS)
        self.key_row_keys = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Đang khởi tạo...", id="stats_panel")
        yield DataTable(id="file_table")
        yield DataTable(id="key_table")
        yield Log(id="sys_log")
        yield Footer()

    def on_mount(self) -> None:
        # Bảng file
        ft = self.query_one("#file_table", DataTable)
        self.f_cols = ft.add_columns("STT", "Tên File", "Trạng Thái", "Key")
        
        # Bảng Key
        kt = self.query_one("#key_table", DataTable)
        self.k_cols = kt.add_columns("Key", "Thử", "Xong", "Status")
        for i in range(len(API_KEYS)):
            rk = kt.add_row(f"#{i+1}", "0", "0", "⚪ Chờ")
            self.key_row_keys.append(rk)

        # Quét file
        sys_log = self.query_one(Log)
        idx = 1
        for root, _, files in sorted(os.walk(self.target_dir)):
            for f in sorted(files):
                if f.endswith((".vtt", ".srt")) and "_vi." not in f:
                    full_path = os.path.join(root, f)
                    vi_file = f.rsplit('.', 1)[0] + '_vi.' + f.rsplit('.', 1)[1]
                    if is_valid_translation(os.path.join(root, vi_file)):
                        ft.add_row(str(idx), f"✅ {f}", "Đã xong", "-")
                    else:
                        rk = ft.add_row(str(idx), f"📄 {f}", "⏳ Chờ", "-")
                        self.missing_files.append({"path": full_path, "row_key": rk, "name": f})
                    idx += 1
        sys_log.write_line(f"[*] Tìm thấy {len(self.missing_files)} file cần dịch.")

    @work(thread=True)
    def action_start_translation(self) -> None:
        sys_log = self.query_one(Log)
        ft = self.query_one("#file_table", DataTable)
        kt = self.query_one("#key_table", DataTable)
        sp = self.query_one("#stats_panel", Static)
        tracker = StatsTracker()

        def ui_log(msg): self.call_from_thread(sys_log.write_line, msg)
        def ui_up_file(rk, col, txt): self.call_from_thread(ft.update_cell, rk, self.f_cols[col], txt)
        def ui_up_key(k_idx, status=None):
            rk = self.key_row_keys[k_idx]
            self.call_from_thread(kt.update_cell, rk, self.k_cols[1], str(self.key_attempts[k_idx]))
            self.call_from_thread(kt.update_cell, rk, self.k_cols[2], str(self.key_success[k_idx]))
            if status: self.call_from_thread(kt.update_cell, rk, self.k_cols[3], status)
        def ui_up_stats(): self.call_from_thread(sp.update, tracker.generate_report())

        bot = TranslatorBot(API_KEYS, ui_log)
        ui_up_key(bot.current_key_index, "🟢 Active")
        ctx = ""

        for item in self.missing_files:
            ui_up_file(item["row_key"], 2, "🔄 Dịch...")
            
            while True:
                try:
                    # ĐẾM NGAY TRƯỚC KHI GỌI API
                    tracker.log_attempt()
                    self.key_attempts[bot.current_key_index] += 1
                    ui_up_key(bot.current_key_index)
                    ui_up_stats()

                    # Check RPM Brake
                    while tracker.get_rpm() >= 14:
                        ui_log("   [!] RPM chạm đỉnh, dừng 5s...")
                        time.sleep(5)
                        ui_up_stats()

                    with open(item["path"], 'r', encoding='utf-8') as f:
                        content = f.read()

                    prompt = f"Dịch phụ đề IT. Ngữ cảnh: {TOPIC}. Thuật ngữ: {GLOSSARY}. Đoạn trước: {ctx[-200:]}.\n\n{content}"
                    response = bot.model.generate_content(prompt, request_options={"timeout": 600})
                    
                    if not response.text: raise Exception("Empty")

                    # Lưu file
                    new_p = item["path"].rsplit('.', 1)[0] + '_vi.' + item["path"].rsplit('.', 1)[1]
                    with open(new_p, 'w', encoding='utf-8') as f:
                        f.write(response.text.strip())
                    
                    # Thành công
                    self.key_success[bot.current_key_index] += 1
                    tracker.total_success += 1
                    ui_up_file(item["row_key"], 1, f"✅ {item['name']}")
                    ui_up_file(item["row_key"], 2, "✅ Xong")
                    ui_up_file(item["row_key"], 3, f"Key_{bot.current_key_index+1}")
                    ui_up_key(bot.current_key_index)
                    
                    ctx = response.text
                    time.sleep(5)
                    break

                except Exception as e:
                    tracker.total_failed += 1
                    err = str(e).lower()
                    if "429" in err or "quota" in err:
                        ui_up_key(bot.current_key_index, "🔴 429")
                        if not bot.rotate_key(): return
                        ui_up_key(bot.current_key_index, "🟢 Active")
                    elif "500" in err or "503" in err or "504" in err:
                        ui_log("   [!] Server lag, chờ 10s...")
                        time.sleep(10)
                    else:
                        ui_up_file(item["row_key"], 2, "❌ Lỗi")
                        break

        ui_log("✅ HOÀN TẤT CHIẾN DỊCH!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--dir", required=True)
    app = TranslatorTUI(target_dir=os.path.abspath(os.path.expanduser(parser.parse_args().dir)))
    app.run()