import requests
import json
import base64
from Crypto.Cipher import AES

# --- CẤU HÌNH ---
# IP máy tính chạy Server (Vì script này chạy trên máy tính nên dùng localhost hoặc IP LAN đều được)
SERVER_URL = "http://192.168.1.67:3000/device-handshake" 

# Khóa AES (Phải khớp với Server)
KEY = b"\x1A\x2B\x3C\x4D\x5E\x6F\x70\x81\x92\xA3\xB4\xC5\xD6\xE7\xF8\x09"
IV  = b"\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99\xAA\xBB\xCC\xDD\xEE\xFF"

def pad(s): return s + (16 - len(s) % 16) * chr(16 - len(s) % 16)

def encrypt_text(plain_text):
    raw = pad(plain_text).encode('utf-8')
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    return base64.b64encode(cipher.encrypt(raw)).decode('utf-8')

# --- BẮT ĐẦU GIẢ LẬP ---
# 1. Tạo một ID thiết bị mới (Bạn có thể đổi số tùy thích)
fake_device_id = "6C:C8:40:34:85:7C" 

print(f"Đang giả lập thiết bị {fake_device_id} kết nối...")

# 2. Đóng gói và mã hóa
payload = json.dumps({"device_id": fake_device_id})
encrypted_data = encrypt_text(payload)

# 3. Gửi lên Server
try:
    response = requests.post(SERVER_URL, data=encrypted_data)
    print("Kết quả Server trả về:", response.status_code)
    print("Nội dung:", response.text)
except Exception as e:
    print("Lỗi:", e)