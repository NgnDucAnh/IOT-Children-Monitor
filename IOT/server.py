from flask import Flask, request, send_from_directory
import os
from datetime import datetime

app = Flask(__name__)
PORT = 3000
UPLOAD_DIR = 'uploads'

# Tạo thư mục uploads nếu chưa có
os.makedirs(UPLOAD_DIR, exist_ok=True)

# === NHẬN ẢNH TỪ ESP32 (RAW JPEG) ===
@app.route('/upload', methods=['POST'])
def upload():
    if not request.data:
        return 'No image data', 400

    # Tạo tên file theo thời gian
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    filename = f"img_{timestamp}.jpg"
    filepath = os.path.join(UPLOAD_DIR, filename)

    # Lưu ảnh
    with open(filepath, 'wb') as f:
        f.write(request.data)

    print(f"Received: {filename} ({len(request.data)} bytes)")
    return '', 200

# === XEM ẢNH MỚI NHẤT ===
@app.route('/latest', methods=['GET'])
def latest():
    files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith('.jpg')]
    if not files:
        return 'No image', 404
    latest_file = sorted(files)[-1]
    return send_from_directory(UPLOAD_DIR, latest_file)

# === CHẠY SERVER ===
if __name__ == '__main__':
    print("="*50)
    print("ESP32-CAM BACKEND (Python Flask)")
    print(f"Server: http://localhost:{PORT}")
    print(f"Upload: POST /upload (raw JPEG)")
    print(f"Latest: GET /latest")
    print("="*50)
    app.run(host='0.0.0.0', port=PORT, debug=False)