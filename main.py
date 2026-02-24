import html
import http.server
import importlib
from importlib import util as importlib_util
import os
import re
import socket
import threading
import urllib.parse
from email.parser import BytesParser
from email.policy import default

cgi = importlib.import_module("cgi") if importlib_util.find_spec("cgi") else None

import customtkinter as ctk
import qrcode
from PIL import Image
from tkinter import filedialog

APP_TITLE = "FileBridge"
WINDOW_SIZE = "860x620"
APPEARANCE_MODE = "dark"
START_BTN_FG = "#16a34a"
START_BTN_HOVER = "#15803d"
STOP_BTN_FG = "#dc2626"
STOP_BTN_HOVER = "#b91c1c"
FONT_MAIN = ("Segoe UI", 14)
FONT_BUTTON = ("Segoe UI", 13, "bold")
QR_SIZE = 260
LOG_HEIGHT = 180

# Вбудований HTML-шаблон веб-сторінки, яку відкривають на смартфоні.
# {notice} та {files} — це плейсхолдери, які сервер підставить динамічно.
HTML_TEMPLATE = """<!doctype html>
<html lang="uk">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>FileBridge</title>
    <link rel="stylesheet" href="/style.css?v=2">
</head>
<body>
    <div class="box">
        <h1>FileBridge</h1>
        <p class="subtitle">Швидкий обмін файлами між телефоном і ПК через Wi‑Fi</p>
        {notice}
        <form class="upload-card" method="POST" enctype="multipart/form-data">
            <label class="file-label">Оберіть файл</label>
            <input type="file" name="file" required>
            <button type="submit">Вибрати файл і завантажити</button>
        </form>
        <h2>Файли на ПК</h2>
        <ul class="files">{files}</ul>
    </div>
</body>
</html>"""



# Вбудований CSS-стиль для веб-інтерфейсу (темна сучасна тема).
CSS_STYLE = """
:root {
    --bg: #0b1220;
    --panel: #111827;
    --panel-2: #0f1b32;
    --text: #e5e7eb;
    --muted: #9ca3af;
    --line: #2a3852;
    --accent: #22c55e;
    --accent-hover: #16a34a;
}

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Segoe UI, Inter, Arial, sans-serif;
    background: radial-gradient(circle at 20% 0%, #12203b 0%, var(--bg) 45%, #090f1d 100%);
    color: var(--text);
    min-height: 100vh;
    padding: 18px 12px;
}

.box {
    max-width: 760px;
    margin: 0 auto;
    padding: 18px;
    background: rgba(17, 24, 39, .95);
    border: 1px solid var(--line);
    border-radius: 16px;
    box-shadow: 0 18px 35px rgba(0, 0, 0, .35);
}

h1 {
    margin: 0;
    font-size: clamp(28px, 5vw, 36px);
}

.subtitle {
    margin: 8px 0 16px;
    color: var(--muted);
    font-size: 15px;
}

.notice {
    margin: 0 0 14px;
    padding: 10px 12px;
    border-radius: 10px;
    border: 1px solid #1f8f57;
    background: #113324;
    color: #9bf5c6;
    font-weight: 600;
}

.notice.error {
    border-color: #9f2832;
    background: #38161a;
    color: #ffb4bb;
}

.upload-card {
    padding: 14px;
    border: 1px dashed #3b4a68;
    border-radius: 12px;
    background: var(--panel-2);
}

.file-label {
    display: block;
    font-size: 14px;
    color: var(--muted);
}

input,
button {
    width: 100%;
    margin-top: 10px;
    font-size: 18px;
}

input {
    color: var(--text);
}

button {
    background: var(--accent);
    color: #fff;
    border: 0;
    padding: 12px;
    border-radius: 10px;
    font-weight: 700;
}

button:hover {
    background: var(--accent-hover);
}

h2 {
    margin: 16px 0 10px;
    font-size: 22px;
}

.files {
    list-style: none;
    padding: 0;
    margin: 0;
}

.files li {
    margin: 7px 0;
}

.files a {
    display: block;
    color: var(--text);
    text-decoration: none;
    padding: 11px 12px;
    background: #0b1324;
    border: 1px solid #273754;
    border-radius: 10px;
    word-break: break-word;
}

.files a:hover {
    border-color: #4f83ff;
    background: #111d35;
}

@media (max-width: 520px) {
    .box {
        padding: 14px;
    }

    button,
    input {
        font-size: 17px;
    }
}
"""

class ReuseableThreadingHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True
    block_on_close = False

class FileBridgeHandler(http.server.SimpleHTTPRequestHandler):
    def _log(self, text):
        if callable(getattr(self.server, "logger", None)):
            self.server.logger(text)

    def _send_html(self, text, code=200):
        data = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_css(self):
        data = CSS_STYLE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/css; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _render_page(self, files_html):
        template = HTML_TEMPLATE
        return template.replace("{files}", files_html).replace("{notice}", getattr(self, "notice_html", ""))
    
    def _redirect_with_notice(self, message, error=False):
        level = "error" if error else "ok"
        encoded = urllib.parse.quote(message)
        self.send_response(303)
        self.send_header("Location", f"/?msg={encoded}&level={level}")
        self.end_headers()

    def _parse_multipart_fallback(self):
        content_type = self.headers.get("Content-Type", "")
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        raw = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf=8") + body
        msg = BytesParser(policy=default).parsebytes(raw)

        if not msg.is_multipart():
            return None, None
        
        for part in msg.iter_parts():
            disp = part.get("Content-Disposition", "")

            if "form-data" in disp and 'name="file"' in disp:
                m = re.search(r'filename="([^"]+)"', disp)

                if not m:
                    return None, None
                
                return m.group(1), part.get_payload(decode=True) or b""
            
        return None, None
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        folder = self.server.upload_dir

        if path == "/style.css":
            self._send_css()
            return
        
        if path.startswith("/files/"):
            name = os.path.basename(urllib.parse.unquote(path.split("/files/", 1)[1]))
            file_path = os.path.join(folder, name)

            if os.path.isfile(file_path):
                with open(file_path, "rb") as f:
                    data = f.read()

                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{name}"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                # write the file data after headers
                self.wfile.write(data)
                return
            
            self.send_error(404, "Файл не найден")
            return
        
        params = urllib.parse.parse_qs(parsed.query)
        msg = params.get("msg", [""])[0].strip()
        level = params.get("level", ["ok"])[0]
        self.notice_html = ""

        if msg:
            safe_msg = html.escape(msg)
            css = "notice error" if level == "error" else "notice"
            self.notice_html = f"<div class='{css}'>{safe_msg}</div>"

        files = []
        for n in sorted(os.listdir(folder), key=str.lower):
            if os.path.isfile(os.path.join(folder, n)):
                files.append(f"<li><a href='/files/{urllib.parse.quote(n)}'>{html.escape(n)}</a></li>")

        files_html = "".join(files) or "<li>Файлов нет</li>"
        self._send_html(self._render_page(files_html))

    def do_POST(self):
        try:
            if cgi is not None:
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={
                        "REQUEST_METHOD": "POST",
                        "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                    },
                )
                
                item = form["file"] if "file" in form else None

                # FieldStorage objects cannot be tested with bool()
                if item is None or not getattr(item, "filename", None):
                    self._redirect_with_notice("Файл не выбран", error=True)
                    return

                name = os.path.basename(item.filename)
                data = item.file.read()
            else:
                filename, data = self._parse_multipart_fallback()

                if not filename:
                    self._redirect_with_notice("Файл не выбран", error=True)
                    return
                
                name = os.path.basename(filename)

            # at this point we have `name` and `data` regardless of branch
            save_path = os.path.join(self.server.upload_dir, name)
            with open(save_path, "wb") as f:
                f.write(data)

            self._log(f"Получен файл {name}")
            self._redirect_with_notice(f"Готово ✅ Файл {name} успешно загружен")

        except OSError:
            self._log("Ошибка доступа")
            self._redirect_with_notice("Ошибка доступа", error=True)

    def log_message(self, fmt, *args):
        self._log("HTTP: " + (fmt % args))

class ServerManager:
    def __init__(self, folder, port, logger):
        self.folder, self.port, self.logger = folder, port, logger
        self.httpd, self.thread = None, None

    def start(self):
        self.httpd = ReuseableThreadingHTTPServer(("0.0.0.0", self.port), FileBridgeHandler)
        self.httpd.upload_dir = self.folder
        self.httpd.logger = self.logger
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=1.5)

            self.httpd, self.thread = None, None

class FileBridgeApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode(APPEARANCE_MODE)
        self.title(APP_TITLE)
        self.geometry(WINDOW_SIZE)
        self.folder, self.port, self.server = os.path.expanduser("~/Download"), 8000, None
        # we'll compute a usable local IP each time the server starts
        self.ip = "127.0.0.1"
        self.is_closing = False
        self._ui()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.log("Готово. Выберите папку и нажмите Start Server.")

    def _ui(self):
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=12, pady=12)

        self.folder_var = ctk.StringVar(value=self.folder)
        ctk.CTkEntry(top, textvariable=self.folder_var, font=FONT_MAIN).pack(side="left", fill="x", expand=True, padx=8, pady=8)
        ctk.CTkButton(top, text="Просмотр", width=90, command=self.pick_folder, font=FONT_BUTTON).pack(side="left", padx=8)

        ctr = ctk.CTkFrame(self)
        ctr.pack(fill="x", padx=12, pady=4)

        self.start_btn = ctk.CTkButton(
            ctr,
            text="Start Server",
            fg_color=START_BTN_FG,
            hover_color=START_BTN_HOVER,
            command=self.start_server,
            font=FONT_BUTTON,
        )
        self.start_btn.pack(side="left", padx=8, pady=8)

        self.stop_btn = ctk.CTkButton(
            ctr,
            text="Stop Server",
            fg_color=STOP_BTN_FG,
            hover_color=STOP_BTN_HOVER,
            state="disabled",
            command=self.stop_server,
            font=FONT_BUTTON,
        )
        self.stop_btn.pack(side="left", padx=8)

        self.url_label = ctk.CTkLabel(ctr, text="URL: сервер не запущен", font=FONT_MAIN)
        self.url_label.pack(side="left", padx=12)

        self.qr_label = ctk.CTkLabel(self, text="QR-код появится здесь после запуска", font=FONT_MAIN)
        self.qr_label.pack(expand=True, pady=8)

        self.log_box = ctk.CTkTextbox(self, height=LOG_HEIGHT, font=FONT_MAIN)
        self.log_box.pack(fill="both", expand=False, padx=12, pady=(0, 12))
        self.log_box.configure(state="disabled")

    def log(self, text):
        if self.is_closing:
            return
        
        try:
            self.after(0, lambda: self._append_log(text))

        except Exception:
            pass

    def _append_log(self, text):
        if self.is_closing:
            return
        
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def pick_folder(self):
        path = filedialog.askdirectory(initialdir=self.folder)

        if path:
            self.folder = path
            self.folder_var.set(path)
            self.log(f"Выбрано папку: {path}")

    def start_server(self):
        if not os.path.isdir(self.folder):
            self.log("Ошибка доступа: папка не существует")
            return
        
        if self.server:
            url = f"http://{self.ip}:{self.port}"
            self._show_qr(url)
            self.log("Сервер уже запущенб QR обновлен")

        # determine a usable LAN address; the socket trick works even when hostname
        # resolves to 127.0.0.1 or some other unwanted value.
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            self.ip = sock.getsockname()[0]
        except Exception:
            self.ip = "127.0.0.1"
        finally:
            try:
                sock.close()
            except Exception:
                pass

        self.server = ServerManager(self.folder, self.port, self.log)

        try:
            self.server.start()

        except OSError as exc:
            self.server = None
            self.log(f"Ошибка запуска сервера: {exc}")
            return
        
        url = f"http://{self.ip}:{self.port}"
        self._show_qr(url)
        self.url_label.configure(text=f"URL: {url}")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.log(f"Сервер запущен на {self.ip}:{self.port}")

    def _show_qr(self, url):
        qr = qrcode.make(url).convert("RGB").resize((QR_SIZE, QR_SIZE), Image.Resampling.LANCZOS)
        self.qr_image = ctk.CTkImage(light_image=qr, dark_image=qr, size=(QR_SIZE, QR_SIZE))
        self.qr_label.configure(image=None, text="")
        self.qr_label.image = self.qr_image
        self.qr_label.configure(image=self.qr_image, text="")

    def stop_server(self):
        server_to_stop = self.server
        self.server = None

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="disabled")
        self.url_label.configure(text="URL: сервер не запущен")
        self.qr_label.configure(text="QR-код появится здесь после запуска", image=None)
        self.qr_label.image = None
        self.qr_image = None

        if not server_to_stop:
            self.start_btn.configure(state="normal")
            self.log("Сервер уже запущен")
            return
        
        try:
            server_to_stop.stop()
            self.log("Сервер остановлен")

        except Exception as exc:
            self.log(f"Ошибка остановки сервера: {exc}")

        finally:
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")

    def _close(self):
        if self.is_closing:
            return
        
        self.is_closing = True
        self.protocol("MW_DELETE_WINDOW", lambda: None)

        server_to_stop = self.server
        self.server = None

        if server_to_stop:
            threading.Thread(target=server_to_stop.stop, daemon=True).start()

        self.destroy()

if __name__ == "__main__":
    app = FileBridgeApp()
    app.mainloop()