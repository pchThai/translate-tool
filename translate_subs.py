import os
import time
import argparse
from collections import deque
from google import genai
from google.genai import types

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Log, Static
from textual import work

# ==========================================
# 1. CẤU HÌNH API & DỊCH THUẬT
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
# 2. CẤU HÌNH LỌC FILE (WHITELIST)
# ==========================================
TARGET_SOURCE_LANGS = ["english", " en.", "-en."] 

def is_valid_source_file(filename):
    filename_lower = filename.lower()
    
    if not filename_lower.endswith((".vtt", ".srt")):
        return False
        
    if "_vi." in filename_lower or ".vi." in filename_lower or "-vi." in filename_lower:
        return False
        
    for lang in TARGET_SOURCE_LANGS:
        if lang in filename_lower:
            return True
            
    return False

# ==========================================
# 3. LOGIC KIỂM TOÁN (DEEP AUDIT)
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
# 4. QUẢN LÝ BOT API
# ==========================================
class TranslatorBot:
    def __init__(self, keys, log_fn):
        self.keys = keys
        self.current_key_index = 0
        self.client = None
        self.failed_cycles = 0
        self.max_cycles = 5
        self.log_fn = log_fn  
        self.setup_client()

    def setup_client(self):
        current_key = self.keys[self.current_key_index]
        # Initialize the new GenAI client
        self.client = genai.Client(api_key=current_key)
        self.log_fn(f"[!] Kích hoạt Key #{self.current_key_index + 1}")

    def generate_content(self, prompt):
        # Using the new client structure
        response = self.client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
        )
        return response

    def rotate_key(self):
        self.current_key_index += 1
        if self.current_key_index >= len(self.keys):
            self.current_key_index = 0
            self.failed_cycles += 1
            self.log_fn(f"\n[♻️] Quay hết 1 vòng các Key. Vòng lỗi: {self.failed_cycles}/{self.max_cycles}")
            time.sleep(30) # Wait longer when all keys exhausted
            
        if self.failed_cycles < self.max_cycles:
            self.setup_client()
            return True
        return False

# ==========================================
# 5. TRACKER (THỐNG KÊ CHI TIẾT)
# ==========================================
class StatsTracker:
    def __init__(self):
        self.all_attempts = deque()
        self.total_success = 0
        self.total_failed = 0
        self.total_tokens = 0

    def log_attempt(self):
        self.all_attempts.append(time.time())
        self.clean_old()

    def add_tokens(self, count):
        self.total_tokens += count

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
        return f"📊 [cyan]Hệ thống:[/] RPM: {rpm_color}{rpm}/15[/] | ✅: [green]{self.total_success}[/] | ❌: [red]{self.total_failed}[/] | 🪙 Tokens: [yellow]{self.total_tokens}[/]"

# ==========================================
# 6. GIAO DIỆN TUI (TEXTUAL)
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
        self.is_running = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Đang khởi tạo...", id="stats_panel")
        yield DataTable(id="file_table")
        yield DataTable(id="key_table")
        yield Log(id="sys_log")
        yield Footer()

    def on_mount(self) -> None:
        ft = self.query_one("#file_table", DataTable)
        self.f_cols = ft.add_columns("STT", "Tên File", "Trạng Thái", "Key")
        
        kt = self.query_one("#key_table", DataTable)
        self.k_cols = kt.add_columns("Key", "Thử", "Xong", "Status")
        for i in range(len(API_KEYS)):
            rk = kt.add_row(f"#{i+1}", "0", "0", "⚪ Chờ")
            self.key_row_keys.append(rk)

        sys_log = self.query_one(Log)
        idx = 1
        
        for root, _, files in sorted(os.walk(self.target_dir)):
            for f in sorted(files):
                if is_valid_source_file(f):
                    full_path = os.path.join(root, f)
                    parts = f.rsplit('.', 1)
                    vi_file = parts[0] + '_vi.' + parts[1]
                    vi_path = os.path.join(root, vi_file)
                    
                    if is_valid_translation(vi_path):
                        ft.add_row(str(idx), f"✅ {f}", "Đã xong", "-")
                    else:
                        rk = ft.add_row(str(idx), f"📄 {f}", "⏳ Chờ", "-")
                        self.missing_files.append({"path": full_path, "row_key": rk, "name": f})
                    idx += 1
                    
        sys_log.write_line(f"[*] Tìm thấy {len(self.missing_files)} file HỢP LỆ cần dịch.")

    @work(thread=True)
    def action_start_translation(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        
        try:
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

            for item in self.missing_files:
                ui_up_file(item["row_key"], 2, "🔄 Dịch...")
                new_p = item["path"].rsplit('.', 1)[0] + '_vi.' + item["path"].rsplit('.', 1)[1]
                
                with open(item["path"], 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                
                blocks = content.split('\n\n')
                chunk_size = 25
                chunks = ["\n\n".join(blocks[i:i + chunk_size]) for i in range(0, len(blocks), chunk_size)]
                
                chunk_idx = 0
                ctx = ""
                retry_count = 0 # Track retries for exponential backoff
                
                if os.path.exists(new_p):
                    os.remove(new_p)

                while chunk_idx < len(chunks):
                    chunk_content = chunks[chunk_idx]
                    
                    try:
                        tracker.log_attempt()
                        self.key_attempts[bot.current_key_index] += 1
                        ui_up_key(bot.current_key_index)
                        ui_up_stats()

                        # Throttle: Ensure we don't exceed 15 RPM
                        while tracker.get_rpm() >= 14:
                            ui_log("   [!] RPM chạm đỉnh, chờ 5s...")
                            time.sleep(5)
                            ui_up_stats()

                        prompt = f"Dịch phụ đề IT. Ngữ cảnh: {TOPIC}. Thuật ngữ: {GLOSSARY}. Đoạn trước: {ctx[-200:]}.\n\n{chunk_content}"
                        
                        # Using the new client method
                        response = bot.generate_content(prompt)
                        
                        if not response.text: raise Exception("Empty")
                        
                        # Track token usage
                        if response.usage_metadata:
                            tracker.add_tokens(response.usage_metadata.total_token_count)

                        with open(new_p, 'a', encoding='utf-8') as f:
                            f.write(response.text.strip() + "\n\n")
                        
                        ctx = response.text
                        chunk_idx += 1  
                        retry_count = 0 # Reset backoff on success
                        time.sleep(4)  # Increased sleep to be safer (15 RPM)
                        ui_up_stats() # Update UI with new token count

                    except Exception as e:
                        err = str(e).lower()
                        if "429" in err or "quota" in err:
                            retry_count += 1
                            backoff = min(60, 2 ** retry_count) # Exponential backoff
                            ui_up_key(bot.current_key_index, f"🔴 429 (Wait {backoff}s)")
                            ui_log(f"   [!] 429 Quota! Chờ {backoff}s và thử lại...")
                            time.sleep(backoff)
                            
                            # Rotate key if we've retried too many times on one key
                            if retry_count > 3:
                                if not bot.rotate_key(): 
                                    ui_log("❌ Hết sạch Key khả dụng. Dừng chương trình.")
                                    return 
                                retry_count = 0
                                ui_up_key(bot.current_key_index, "🟢 Active")
                        
                        elif "500" in err or "503" in err or "504" in err:
                            ui_log("   [!] Server lag, chờ 10s...")
                            time.sleep(10)
                        else:
                            tracker.total_failed += 1
                            ui_up_file(item["row_key"], 2, "❌ Lỗi")
                            ui_log(f"   [!] Lỗi không xác định: {e}")
                            break 

                if chunk_idx == len(chunks):
                    self.key_success[bot.current_key_index] += 1
                    tracker.total_success += 1
                    ui_up_file(item["row_key"], 1, f"✅ {item['name']}")
                    ui_up_file(item["row_key"], 2, "✅ Xong")
                    ui_up_file(item["row_key"], 3, f"Key_{bot.current_key_index+1}")
                    ui_up_key(bot.current_key_index)

            ui_log("✅ HOÀN TẤT CHIẾN DỊCH!")
        finally:
            self.is_running = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--dir", required=True)
    app = TranslatorTUI(target_dir=os.path.abspath(os.path.expanduser(parser.parse_args().dir)))
    app.run()
