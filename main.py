import os
import sys
import socket
import webbrowser
import threading
import tkinter as tk
from tkinter import messagebox
from PIL import ImageTk, Image
from flask import Flask, request, send_from_directory, render_template_string, jsonify, send_file
from zipfile import ZipFile
from io import BytesIO
import qrcode

# ==================== 路径自适应配置 ====================
def get_base_path():
    """获取程序运行时的物理目录，确保打包后文件夹在 EXE 旁边"""
    if hasattr(sys, '_MEIPASS'):
        # 打包后的环境下，sys.executable 是 exe 的路径
        return os.path.dirname(os.path.realpath(sys.executable))
    # 开发环境下，使用脚本路径
    return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()
UPLOAD_FOLDER = os.path.join(BASE_PATH, 'uploads')

# 确保 uploads 目录存在
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'

LOCAL_IP = get_local_ip()
PORT = 5000
BASE_URL = f"http://{LOCAL_IP}:{PORT}/"

# ==================== 极简前端模板 ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>文件传输助手</title>
    <style>
        :root { --primary: #2563eb; --danger: #dc2626; --bg: #f3f4f6; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, -apple-system, sans-serif; background: var(--bg); color: #1f2937; line-height: 1.5; }
        .container { max-width: 800px; margin: 40px auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
        h1 { text-align: center; margin-bottom: 24px; font-weight: 600; }
        .upload-area { border: 2px dashed #d1d5db; border-radius: 8px; padding: 40px; text-align: center; cursor: pointer; background: #fafafa; transition: 0.2s; margin-bottom: 30px; }
        .upload-area:hover { border-color: var(--primary); background: #f0f7ff; }
        .toolbar { display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; }
        button, .btn { padding: 8px 16px; border: 1px solid #e5e7eb; border-radius: 6px; cursor: pointer; font-size: 14px; background: white; transition: 0.2s; }
        button:hover { background: #f9fafb; }
        .btn-primary { background: var(--primary); color: white; border: none; }
        .btn-primary:hover { background: #1d4ed8; }
        .btn-danger { color: var(--danger); }
        .btn-danger:hover { background: #fef2f2; }
        .file-item { display: flex; align-items: center; padding: 12px; border-bottom: 1px solid #f3f4f6; }
        .file-item:last-child { border-bottom: none; }
        .file-name { flex: 1; margin: 0 15px; font-size: 14px; word-break: break-all; }
        .file-size { color: #6b7280; font-size: 12px; width: 80px; text-align: right; }
        .checkbox { width: 18px; height: 18px; cursor: pointer; }
        input[type="file"] { display: none; }
        .toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: #374151; color: white; padding: 8px 20px; border-radius: 20px; font-size: 14px; opacity: 0; transition: 0.3s; pointer-events: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>文件传输助手</h1>
        <div class="upload-area" id="dropZone">
            <p>点击或拖拽文件到这里上传</p>
            <input type="file" id="fileInput" multiple>
        </div>
        <div class="toolbar">
            <button onclick="toggleAll(true)">全选</button>
            <button onclick="toggleAll(false)">取消</button>
            <button class="btn-danger" onclick="batchDelete()">删除选中</button>
            <button class="btn-primary" style="margin-left: auto" onclick="batchDownload()">打包下载</button>
        </div>
        <div id="fileList"></div>
    </div>
    <div id="toast" class="toast"></div>

    <script>
        let selectedFiles = new Set();

        function showToast(msg) {
            const t = document.getElementById('toast');
            t.textContent = msg; t.style.opacity = 1;
            setTimeout(() => t.style.opacity = 0, 2000);
        }

        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('fileInput');
        dropZone.onclick = () => fileInput.click();
        fileInput.onchange = (e) => handleUpload(e.target.files);

        function handleUpload(files) {
            if (!files.length) return;
            const fd = new FormData();
            Array.from(files).forEach(f => fd.append('files', f));
            fetch('/upload', { method: 'POST', body: fd })
                .then(r => r.json()).then(data => {
                    showToast(data.msg);
                    loadFiles();
                });
        }

        function toggleAll(checked) {
            const cbs = document.querySelectorAll('.checkbox');
            cbs.forEach(cb => {
                cb.checked = checked;
                updateSet(cb);
            });
        }

        function updateSet(cb) {
            if (cb.checked) selectedFiles.add(cb.dataset.name);
            else selectedFiles.delete(cb.dataset.name);
        }

        function loadFiles() {
            fetch('/file_list').then(r => r.json()).then(data => {
                const container = document.getElementById('fileList');
                if (!data.files.length) {
                    container.innerHTML = '<p style="text-align:center;color:#999;padding:20px;">空空如也</p>';
                    return;
                }
                container.innerHTML = data.files.map(f => `
                    <div class="file-item">
                        <input type="checkbox" class="checkbox" data-name="${f.name}" 
                            ${selectedFiles.has(f.name) ? 'checked' : ''} onchange="updateSet(this)">
                        <div class="file-name">${f.name}</div>
                        <div class="file-size">${(f.size/1024/1024).toFixed(2)} MB</div>
                        <a href="/download/${encodeURIComponent(f.name)}" style="text-decoration:none;font-size:13px;color:var(--primary)">下载</a>
                    </div>
                `).join('');
            });
        }

        function batchDelete() {
            if (!selectedFiles.size) return showToast('请先勾选');
            if (!confirm(\`确定删除这 \${selectedFiles.size} 个文件?\`)) return;
            fetch('/batch_delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ files: Array.from(selectedFiles) })
            }).then(() => {
                selectedFiles.clear();
                loadFiles();
                showToast('已删除');
            });
        }

        function batchDownload() {
            if (!selectedFiles.size) return showToast('请先勾选');
            const form = document.createElement('form');
            form.method = 'POST'; form.action = '/batch_download';
            selectedFiles.forEach(f => {
                const input = document.createElement('input');
                input.type = 'hidden'; input.name = 'files'; input.value = f;
                form.appendChild(input);
            });
            document.body.appendChild(form); form.submit(); document.body.removeChild(form);
        }

        loadFiles();
        setInterval(loadFiles, 5000);
    </script>
</body>
</html>
"""

# ==================== Flask 路由逻辑 ====================
@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@app.route('/upload', methods=['POST'])
def upload():
    files = request.files.getlist('files')
    for file in files:
        if file.filename:
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
    return jsonify({'status': 'success', 'msg': f'成功上传 {len(files)} 个文件'})

@app.route('/file_list')
def file_list():
    files = []
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        for f in os.listdir(app.config['UPLOAD_FOLDER']):
            p = os.path.join(app.config['UPLOAD_FOLDER'], f)
            if os.path.isfile(p):
                files.append({'name': f, 'size': os.path.getsize(p), 'mtime': os.path.getmtime(p)})
    files.sort(key=lambda x: x['mtime'], reverse=True)
    return jsonify({'files': files})

@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/batch_delete', methods=['POST'])
def batch_delete():
    data = request.get_json()
    for f in data.get('files', []):
        p = os.path.join(app.config['UPLOAD_FOLDER'], f)
        if os.path.exists(p): os.remove(p)
    return jsonify({'status': 'success', 'msg': '已删除'})

@app.route('/batch_download', methods=['POST'])
def batch_download():
    files = request.form.getlist('files')
    mem = BytesIO()
    with ZipFile(mem, 'w') as zf:
        for f in files:
            p = os.path.join(app.config['UPLOAD_FOLDER'], f)
            if os.path.isfile(p): zf.write(p, arcname=f)
    mem.seek(0)
    return send_file(mem, mimetype='application/zip', as_attachment=True, download_name='batch_files.zip')

# ==================== Tkinter 控制中心 ====================
def start_control_panel():
    root = tk.Tk()
    root.title("文件传输控制台")
    root.geometry("300x420")
    root.resizable(False, False)

    # 生成二维码
    qr = qrcode.QRCode(box_size=5, border=2)
    qr.add_data(BASE_URL)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    buf = BytesIO()
    qr_img.save(buf, format='PNG')
    buf.seek(0)
    img = Image.open(buf)
    tk_img = ImageTk.PhotoImage(img)

    tk.Label(root, text="手机扫码访问:", font=("Arial", 10)).pack(pady=10)
    qr_label = tk.Label(root, image=tk_img)
    qr_label.image = tk_img 
    qr_label.pack()

    tk.Label(root, text=BASE_URL, fg="blue", font=("Arial", 9), wraplength=250).pack(pady=5)

    tk.Button(root, text="在浏览器打开", command=lambda: webbrowser.open(BASE_URL), 
              bg="#2563eb", fg="white", width=20, pady=5).pack(pady=10)
    
    tk.Button(root, text="打开存储目录", command=lambda: os.startfile(UPLOAD_FOLDER), 
              width=20, pady=5).pack()

    def on_closing():
        if messagebox.askokcancel("退出", "确定要关闭文件传输服务吗？"):
            os._exit(0)

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

# ==================== 启动逻辑 ====================
if __name__ == '__main__':
    # Flask 启动线程
    flask_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False),
        daemon=True
    )
    flask_thread.start()

    # 稍等一下再打开网页，确保服务已启动
    threading.Timer(1.0, lambda: webbrowser.open(BASE_URL)).start()

    print(f"服务已启动: {BASE_URL}")
    print(f"存储路径: {UPLOAD_FOLDER}")
    
    start_control_panel()
