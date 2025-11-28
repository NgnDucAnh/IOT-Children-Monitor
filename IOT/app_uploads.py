# import os
# import base64
# import json
# import time
# import threading
# from datetime import datetime
# from flask import Flask, request, jsonify
# from openai import OpenAI
# from dotenv import load_dotenv
# import boto3
# from Crypto.Cipher import AES

# # --- THƯ VIỆN FIREBASE ---
# import firebase_admin
# from firebase_admin import credentials, firestore

# # ================= CẤU HÌNH =================
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# load_dotenv(os.path.join(BASE_DIR, '.env'))

# # 1. Cấu hình Firebase
# # Tải file này từ Firebase Console -> Project Settings -> Service Accounts
# cred = credentials.Certificate(os.path.join(BASE_DIR, "creds.json"))
# firebase_admin.initialize_app(cred)
# db = firestore.client()

# # 2. Cấu hình AWS S3 & OpenAI
# S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
# AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
# AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
# AWS_REGION = os.getenv("AWS_REGION")
# api_key = os.getenv("OPENAI_API_KEY")

# s3_client = boto3.client('s3',
#     aws_access_key_id=AWS_ACCESS_KEY_ID,
#     aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
#     region_name=AWS_REGION
# )
# client = OpenAI(api_key=api_key)

# # 3. Cấu hình Mã Hóa (AES-128) - KHÓA PHẢI GIỐNG ESP32
# KEY = b"\x1A\x2B\x3C\x4D\x5E\x6F\x70\x81\x92\xA3\xB4\xC5\xD6\xE7\xF8\x09"
# IV  = b"\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99\xAA\xBB\xCC\xDD\xEE\xFF"

# app = Flask(__name__)
# PORT = 3000

# # ================= HÀM MÃ HÓA / GIẢI MÃ =================

# def create_presigned_url(filename, expiration=3600):
#     """Tạo URL tạm thời để App xem được ảnh trên S3"""
#     try:
#         response = s3_client.generate_presigned_url('get_object',
#                                                     Params={'Bucket': S3_BUCKET_NAME,
#                                                             'Key': f'{S3_IMAGE_FOLDER}/{filename}'},
#                                                     ExpiresIn=expiration)
#     except ClientError as e:
#         print(f"Lỗi tạo link S3: {e}")
#         return None
#     return response

# def pad(s):
#     return s + (16 - len(s) % 16) * chr(16 - len(s) % 16)

# def unpad(s):
#     return s[:-ord(s[len(s)-1:])]

# def encrypt_text(plain_text):
#     try:
#         raw = pad(plain_text).encode('utf-8')
#         cipher = AES.new(KEY, AES.MODE_CBC, IV)
#         encrypted = cipher.encrypt(raw)
#         return base64.b64encode(encrypted).decode('utf-8')
#     except Exception as e:
#         print(f"Encrypt Error: {e}")
#         return None

# def decrypt_text(encrypted_b64):
#     try:
#         enc = base64.b64decode(encrypted_b64)
#         cipher = AES.new(KEY, AES.MODE_CBC, IV)
#         decrypted = cipher.decrypt(enc)
#         return unpad(decrypted.decode('utf-8'))
#     except Exception as e:
#         print(f"Decrypt Error: {e}")
#         return None

# def decrypt_image(encrypted_b64):
#     try:
#         data = base64.b64decode(encrypted_b64)
#         cipher = AES.new(KEY, AES.MODE_CBC, IV)
#         decrypted = cipher.decrypt(data)
#         # Xử lý unpad thủ công cho binary
#         pad_len = decrypted[-1]
#         if pad_len < 1 or pad_len > 16: pad_len = 0
#         return decrypted[:-pad_len] if pad_len else decrypted
#     except Exception as e:
#         print("Image Decrypt Error:", e)
#         return None

# # ================= LOGIC XỬ LÝ AI & LOGS =================
# ACTION_LABELS = ["writing", "reading", "sleeping", "using_computer", "using_phone", "no_person", "other_action"]

# def process_image_ai(filename, device_id):
#     """Gửi ảnh cho OpenAI phân tích và lưu log vào Firebase"""
#     temp_path = os.path.join(BASE_DIR, 'temp_ai', filename)
#     os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    
#     try:
#         # 1. Tải ảnh từ S3 về để gửi cho GPT (hoặc gửi URL nếu public)
#         s3_key = f'IOT/images/{filename}'
#         s3_client.download_file(S3_BUCKET_NAME, s3_key, temp_path)
        
#         with open(temp_path, "rb") as f:
#             b64_img = base64.b64encode(f.read()).decode('utf-8')

#         response = client.chat.completions.create(
#             model="gpt-4o",
#             messages=[
#                 {"role": "system", "content": f"Return only one label: {', '.join(ACTION_LABELS)}"},
#                 {"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}]}
#             ],
#             max_tokens=20
#         )
#         action = response.choices[0].message.content.strip().replace('"','').replace('.','')
#         if action not in ACTION_LABELS: action = "unknown_action"

#         # 2. Lấy config của thiết bị từ Firebase để xem có cần báo động không
#         device_ref = db.collection('devices').document(device_id)
#         dev_doc = device_ref.get()
#         is_alert = False
        
#         if dev_doc.exists:
#             config = dev_doc.to_dict().get('config', {})
#             # Nếu hành động nằm trong config và giá trị là True thì báo động
#             if config.get(action, False):
#                 is_alert = True

#         # 3. Lưu Log vào Firebase sub-collection 'logs' của device
#         log_data = {
#             "timestamp": firestore.SERVER_TIMESTAMP,
#             "action_code": action,
#             "image_filename": filename,
#             "is_alert": is_alert
#         }
#         device_ref.collection('logs').add(log_data)
        
#         # Cập nhật trạng thái mới nhất cho device
#         device_ref.update({"latest_log": log_data})
        
#         print(f"AI Result [{device_id}]: {action} | Alert: {is_alert}")

#     except Exception as e:
#         print(f"AI Processing Error: {e}")
#     finally:
#         if os.path.exists(temp_path): os.remove(temp_path)

# # ================= API ENDPOINTS =================

# # 1. API: Mobile App gọi để bắt đầu chế độ ghép đôi// API 1:
# # //{
# #     "user_id": "test_user_bang_postman"
# # }

# #  { "user_id": "test_user_bang_postman", "device_id": "6C:C8:40:34:85:7C" }
# @app.route('/api/start-pairing', methods=['POST'])
# def start_pairing():
#     data = request.json
#     user_id = data.get('user_id')
#     if not user_id: return jsonify({"error": "missing user_id"}), 400
#     db.collection('pairing_queue').document(user_id).set({
#         'user_id': user_id,
#         'timestamp': firestore.SERVER_TIMESTAMP,
#         'status': 'waiting'
#     })
#     return jsonify({"status": "waiting", "message": "Ready to pair device"}), 200

# # 2. API: ESP32 gọi để xác thực (Handshake)
# @app.route('/device-handshake', methods=['POST'])
# def handshake():
#     encrypted_data = request.data.decode('utf-8')
#     decrypted_json = decrypt_text(encrypted_data)
    
#     if not decrypted_json:
#         return jsonify({"status": "error"}), 400

#     try:
#         info = json.loads(decrypted_json)
#         mac = info.get('device_id')
#     except:
#         return jsonify({"status": "error"}), 400

#     device_ref = db.collection('devices').document(mac)
#     doc = device_ref.get()
    
#     response_data = {}

#     if doc.exists:
#         # Đã đăng ký -> Trả về cấu hình
#         data = doc.to_dict()
#         response_data = {
#             "status": "authorized",
#             "owner": data.get('user_id'),
#             "config": data.get('config', {})
#         }
#     else:
#         # Chưa đăng ký -> Tìm trong hàng đợi
#         queues = db.collection('pairing_queue').where('status', '==', 'waiting').limit(1).stream()
#         found_user = None
#         for q in queues:
#             found_user = q.to_dict().get('user_id')
#             db.collection('pairing_queue').document(found_user).delete() # Xóa khỏi hàng đợi
#             break
        
#         if found_user:
#             # Tạo thiết bị mới
#             default_config = {"sleeping": True, "using_phone": True, "no_person": True}
#             device_ref.set({
#                 'mac_address': mac,
#                 'user_id': found_user,
#                 'config': default_config,
#                 'created_at': firestore.SERVER_TIMESTAMP
#             })
#             response_data = {"status": "registered_success", "config": default_config}
#         else:
#             response_data = {"status": "unauthorized"}

#     # Trả về kết quả mã hóa
#     return encrypt_text(json.dumps(response_data))

# # 3. API: ESP32 gửi ảnh (Mã hóa)
# @app.route('/upload', methods=['POST'])
# def upload():
#     # Header chứa Device ID để định danh (ESP32 gửi kèm)
#     device_id = request.headers.get('Device-ID') 
    
#     encrypted_b64 = request.data.decode('utf-8')
#     raw_image = decrypt_image(encrypted_b64)
    
#     if not raw_image: return 'Decrypt Failed', 400

#     # Upload lên S3
#     filename = f"img_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
#     s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=f'IOT/images/{filename}', Body=raw_image, ContentType='image/jpeg')
    
#     # Chạy AI ngầm
#     if device_id:
#         threading.Thread(target=process_image_ai, args=(filename, device_id)).start()
    
#     return 'Upload OK', 200

# # 4. API: ESP32 lấy kết quả hành động mới nhất (Polling)
# @app.route('/results', methods=['GET'])
# def results():
#     device_id = request.args.get('device_id')
#     if not device_id: 
#         return jsonify({"error": "missing device_id"}), 400
    
#     # Lấy dữ liệu từ Firebase
#     doc = db.collection('devices').document(device_id).get()
    
#     if doc.exists:
#         data = doc.to_dict()
#         latest = data.get('latest_log', {}) # Lấy log mới nhất
        
#         # --- BẮT ĐẦU PHẦN SỬA ĐỔI ---
#         # Kiểm tra xem log có tên file ảnh không
#         if latest and 'image_filename' in latest:
#             filename = latest['image_filename']
            
#             # Gọi hàm tạo link S3 (Hàm này đã có sẵn ở đầu file app_uploads.py của bạn)
#             # Link này sẽ giúp Android tải được ảnh
#             image_url = create_presigned_url(filename) 
            
#             # Thêm trường image_url vào kết quả trả về
#             latest['image_url'] = image_url
#         # ----------------------------

#         return jsonify({
#             "status": "success",
#             "latest_action": latest,
#             "current_config": data.get('config', {})
#         })
    
#     return jsonify({"status": "empty", "latest_action": None})

# @app.route('/api/admin/all-devices', methods=['GET'])
# def get_all_devices():
#     try:
#         docs = db.collection('devices').stream()
#         devices = []
#         for doc in docs:
#             d = doc.to_dict()
#             # Thêm ID của document vào dữ liệu trả về để dễ nhìn
#             d['device_id'] = doc.id 
#             devices.append(d)
        
#         return jsonify({
#             "status": "success",
#             "count": len(devices),
#             "devices": devices
#         }), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# # 6. API: Xem chi tiết thông tin của MỘT thiết bị cụ thể
# # URL: http://<IP>:3000/api/device-info/<device_id>
# @app.route('/api/device-info/<device_id>', methods=['GET'])
# def get_device_info(device_id):
#     try:
#         # Tìm trong collection 'devices'
#         doc_ref = db.collection('devices').document(device_id)
#         doc = doc_ref.get()

#         if doc.exists:
#             data = doc.to_dict()
            
#             # Lấy thêm logs (lịch sử hoạt động) của thiết bị này (nếu cần)
#             # logs_ref = doc_ref.collection('logs').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(5).stream()
#             # logs = [l.to_dict() for l in logs_ref]
#             # data['recent_logs'] = logs

#             return jsonify({
#                 "status": "success",
#                 "device_id": device_id,
#                 "data": data
#             }), 200
#         else:
#             return jsonify({
#                 "status": "error",
#                 "message": f"Không tìm thấy thiết bị có ID: {device_id}"
#             }), 404
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500
# # ================= API: KIỂM TRA QUYỀN SỞ HỮU & LẤY THÔNG TIN USER =================
# # URL: http://<IP>:3000/api/check-ownership
# # Method: POST
# # Body: { "user_id": "test_user_bang_postman", "device_id": "6C:C8:40:34:85:7C" }

# #  {
# #    # Body: { "user_id": "test_user_bang_postman", "device_id": "6C:C8:40:34:85:7C" } 

# #  }
# @app.route('/api/check-ownership', methods=['POST'])
# def check_ownership():
#     # 1. Lấy dữ liệu từ App gửi lên
#     data = request.json
#     request_user_id = data.get('user_id')
#     request_device_id = data.get('device_id')

#     if not request_user_id or not request_device_id:
#         return jsonify({"status": "error", "message": "Thiếu user_id hoặc device_id"}), 400

#     try:
#         # 2. Tìm thiết bị trong Database
#         device_ref = db.collection('devices').document(request_device_id)
#         device_doc = device_ref.get()

#         if not device_doc.exists:
#             return jsonify({"status": "error", "message": "Thiết bị không tồn tại"}), 404
        
#         # 3. Lấy thông tin chủ sở hữu thực sự của thiết bị
#         device_data = device_doc.to_dict()
#         real_owner = device_data.get('user_id')

#         # 4. SO SÁNH (Logic bạn yêu cầu)
#         if real_owner == request_user_id:
#             # === TRƯỜNG HỢP KHỚP: ĐƯỢC PHÉP SỬ DỤNG ===
            
#             # (Tùy chọn) Lấy thêm thông tin chi tiết user nếu bạn có bảng 'users' riêng
#             # user_info = db.collection('users').document(request_user_id).get().to_dict()
            
#             return jsonify({
#                 "status": "allowed",
#                 "message": "Xác thực thành công. Người dùng có quyền điều khiển.",
#                 "user_info": {
#                     "user_id": request_user_id,
#                     "role": "owner",
#                     "device_config": device_data.get('config') # Trả về cấu hình để App hiển thị
#                 }
#             }), 200
#         else:
#             # === TRƯỜNG HỢP KHÔNG KHỚP: TỪ CHỐI ===
#             return jsonify({
#                 "status": "denied",
#                 "message": "CẢNH BÁO: Thiết bị này thuộc về người khác!",
#                 "current_owner": "Ẩn danh" # Không nên trả về ID người khác vì bảo mật
#             }), 403

#     except Exception as e:
#         return jsonify({"status": "error", "message": str(e)}), 500
    
# # //   "status": "allowed",
# #                 "message": "Xác thực thành công. Người dùng có quyền điều khiển.",
# #                 "user_info": {
                   
# #                     "user_id": request_user_id,
# #                     "role": "owner",
# #                     "device_config": device_data.get('config') # Trả về cấu hình để App hiển thị
# #                 }
# # Neu message =="Xác thực thành công. Người dùng có quyền điều khiển.", -> main
# # Neu message ==CẢNH BÁO: Thiết bị này thuộc về người khác!",, -> xác thực


# # API: Lấy danh sách thiết bị của User (Để App quyết định vào Main hay Pairing)
# @app.route('/api/get-my-devices', methods=['POST'])
# def get_my_devices():
#     user_id = request.json.get('user_id')
    
#     if not user_id:
#         return jsonify({"status": "error", "message": "Missing user_id"}), 400

#     try:
#         # Tìm tất cả thiết bị mà user_id này đứng tên
#         docs = db.collection('devices').where('user_id', '==', user_id).stream()
        
#         my_devices = []
#         for doc in docs:
#             d = doc.to_dict()
#             # Chỉ lấy những thông tin cần thiết trả về cho App
#             my_devices.append({
#                 "device_id": doc.id,         # <--- App sẽ lấy ID này để lưu lại
#                 "config": d.get('config'),
#                 "created_at": d.get('created_at')
#             })
            
#         return jsonify({
#             "status": "success", 
#             "count": len(my_devices),
#             "devices": my_devices
#         }), 200
        
#     except Exception as e:
#         return jsonify({"status": "error", "message": str(e)}), 500

# if __name__ == '__main__':
#     print("SERVER STARTED - FIREBASE & AES ENABLED")
#     app.run(host='0.0.0.0', port=3000, debug=True)

import os
import base64
import json
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import boto3
from Crypto.Cipher import AES
from botocore.exceptions import ClientError # Thêm thư viện này để xử lý lỗi AWS S3

# --- THƯ VIỆN FIREBASE ---
import firebase_admin
from firebase_admin import credentials, firestore

# ================= CẤU HÌNH =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# 1. Cấu hình Firebase
# Tải file này từ Firebase Console -> Project Settings -> Service Accounts
cred = credentials.Certificate(os.path.join(BASE_DIR, "creds.json"))
firebase_admin.initialize_app(cred)
db = firestore.client()

# 2. Cấu hình AWS S3 & OpenAI
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
api_key = os.getenv("OPENAI_API_KEY")

# >>> FIX LỖI: Định nghĩa biến bị thiếu <<<
S3_IMAGE_FOLDER = "IOT/images" 

s3_client = boto3.client('s3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)
client = OpenAI(api_key=api_key)

# 3. Cấu hình Mã Hóa (AES-128) - KHÓA PHẢI GIỐNG ESP32
KEY = b"\x1A\x2B\x3C\x4D\x5E\x6F\x70\x81\x92\xA3\xB4\xC5\xD6\xE7\xF8\x09"
IV = b"\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99\xAA\xBB\xCC\xDD\xEE\xFF"

app = Flask(__name__)
PORT = 3000

# ================= HÀM MÃ HÓA / GIẢI MÃ =================

def create_presigned_url(filename, expiration=3600):
    """Tạo URL tạm thời để App xem được ảnh trên S3"""
    try:
        response = s3_client.generate_presigned_url('get_object',
                                                     Params={'Bucket': S3_BUCKET_NAME,
                                                             'Key': f'{S3_IMAGE_FOLDER}/{filename}'},
                                                     ExpiresIn=expiration)
    except ClientError as e:
        print(f"Lỗi tạo link S3: {e}")
        return None
    return response

def pad(s):
    return s + (16 - len(s) % 16) * chr(16 - len(s) % 16)

def unpad(s):
    return s[:-ord(s[len(s)-1:])]

def encrypt_text(plain_text):
    try:
        raw = pad(plain_text).encode('utf-8')
        cipher = AES.new(KEY, AES.MODE_CBC, IV)
        encrypted = cipher.encrypt(raw)
        return base64.b64encode(encrypted).decode('utf-8')
    except Exception as e:
        print(f"Encrypt Error: {e}")
        return None

def decrypt_text(encrypted_b64):
    try:
        enc = base64.b64decode(encrypted_b64)
        cipher = AES.new(KEY, AES.MODE_CBC, IV)
        decrypted = cipher.decrypt(enc)
        return unpad(decrypted.decode('utf-8'))
    except Exception as e:
        print(f"Decrypt Error: {e}")
        return None

def decrypt_image(encrypted_b64):
    try:
        data = base64.b64decode(encrypted_b64)
        cipher = AES.new(KEY, AES.MODE_CBC, IV)
        decrypted = cipher.decrypt(data)
        # Xử lý unpad thủ công cho binary
        pad_len = decrypted[-1]
        if pad_len < 1 or pad_len > 16: pad_len = 0
        return decrypted[:-pad_len] if pad_len else decrypted
    except Exception as e:
        print("Image Decrypt Error:", e)
        return None

# ================= LOGIC XỬ LÝ AI & LOGS =================
ACTION_LABELS = ["writing", "reading", "sleeping", "using_computer", "using_phone", "no_person", "other_action"]

# def process_image_ai(filename, device_id):
#     """Gửi ảnh cho OpenAI phân tích và lưu log vào Firebase"""
#     temp_path = os.path.join(BASE_DIR, 'temp_ai', filename)
#     os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    
#     try:
#         # 1. Tải ảnh từ S3 về
#         s3_key = f'{S3_IMAGE_FOLDER}/{filename}'
#         s3_client.download_file(S3_BUCKET_NAME, s3_key, temp_path)
        
#         with open(temp_path, "rb") as f:
#             b64_img = base64.b64encode(f.read()).decode('utf-8')

#         # 2. Gửi cho AI
#         response = client.chat.completions.create(
#             model="gpt-4o",
#             messages=[
#                 {"role": "system", "content": f"Return only one label: {', '.join(ACTION_LABELS)}"},
#                 {"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}]}
#             ],
#             max_tokens=20
#         )
#         action = response.choices[0].message.content.strip().replace('"','').replace('.','')
#         if action not in ACTION_LABELS: action = "unknown_action"

#         # 3. Lấy config từ Firebase (LOGIC MỚI - CÓ ƯU TIÊN MASTER SWITCH)
#         device_ref = db.collection('devices').document(device_id)
#         dev_doc = device_ref.get()
        
#         # Mặc định tắt hết
#         trigger_light = False
#         trigger_buzzer = False
#         is_alert = False
        
#         if dev_doc.exists:
#             full_config = dev_doc.to_dict().get('config', {})
            
#             # Lấy cấu hình chung (Master switch)
#             general_settings = full_config.get('general', {})
#             master_light = general_settings.get('master_light', True)   # Còi chung
#             master_buzzer = general_settings.get('master_buzzer', True) # Đèn chung

#             # Lấy cấu hình riêng cho hành động này
#             action_settings = full_config.get(action, {})

#             # --- LOGIC QUYẾT ĐỊNH ---
            
#             # 1. Xử lý ĐÈN: Chỉ bật khi (Đèn chung BẬT) VÀ (Đèn hành động này BẬT)
#             if master_light: 
#                 if action_settings.get('enable_light', False):
#                     trigger_light = True
            
#             # 2. Xử lý CÒI: Chỉ bật khi (Còi chung BẬT) VÀ (Còi hành động này BẬT)
#             if master_buzzer:
#                 if action_settings.get('enable_buzzer', False):
#                     trigger_buzzer = True

#             # 3. Kết luận có phải cảnh báo không
#             if trigger_light or trigger_buzzer:
#                 is_alert = True

#         # 4. Lưu Log vào Firebase
#         log_data = {
#             "timestamp": firestore.SERVER_TIMESTAMP,
#             "action_code": action,
#             "image_filename": filename,
#             "is_alert": is_alert,
#             "trigger_light": trigger_light,
#             "trigger_buzzer": trigger_buzzer
#         }
#         device_ref.collection('logs').add(log_data)
#         device_ref.update({"latest_log": log_data})
        
#         print(f"AI Result [{device_id}]: {action} | Light: {trigger_light} | Buzzer: {trigger_buzzer}")

#     except Exception as e:
#         print(f"AI Processing Error: {e}")
#     finally:
#         if os.path.exists(temp_path): os.remove(temp_path)

# --- HÀM PHỤ TRỢ: KIỂM TRA GIỜ ---
def is_time_in_range(start_str, end_str):
    """Kiểm tra giờ hiện tại có nằm trong khoảng cho phép không"""
    try:
        now = datetime.now().time()
        start = datetime.strptime(start_str, "%H:%M").time()
        end = datetime.strptime(end_str, "%H:%M").time()
        
        # Xử lý trường hợp qua đêm (VD: 22:00 đến 06:00 sáng hôm sau)
        if start <= end:
            return start <= now <= end
        else:
            # Qua đêm: Hoặc là lớn hơn start (23:00) HOẶC nhỏ hơn end (05:00)
            return start <= now or now <= end
    except Exception as e:
        print(f"Lỗi format giờ: {e}")
        return True # Nếu lỗi định dạng thì mặc định cho phép chạy để tránh lỗi hệ thống

# --- HÀM XỬ LÝ CHÍNH ĐÃ CẬP NHẬT ---
# --- HÀM XỬ LÝ CHÍNH ĐÃ NÂNG CẤP ---
def process_image_ai(filename, device_id):
    """Gửi ảnh cho OpenAI phân tích và lưu log vào Firebase"""
    temp_path = os.path.join(BASE_DIR, 'temp_ai', filename)
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    
    try:
        # 1. Tải ảnh từ S3 về để xử lý (hoặc xóa nếu không cần)
        s3_key = f'{S3_IMAGE_FOLDER}/{filename}'
        
        # Lấy config từ Firebase trước khi làm gì cả
        device_ref = db.collection('devices').document(device_id)
        dev_doc = device_ref.get()
        
        if dev_doc.exists:
            full_config = dev_doc.to_dict().get('config', {})

            # ========================================================
            # [LOGIC MỚI] KIỂM TRA LỊCH TRÌNH (SCHEDULE)
            # ========================================================
            schedule = full_config.get('schedule', {})
            if schedule.get('enabled', False):
                start_time = schedule.get('start_time', "00:00")
                end_time = schedule.get('end_time', "23:59")
                
                # Nếu NGOÀI giờ hoạt động
                if not is_time_in_range(start_time, end_time):
                    print(f"[{device_id}] Ngoài giờ hoạt động. Tắt báo động.")
                    
                    # Tạo trạng thái "Yên lặng"
                    quiet_log = {
                        "timestamp": firestore.SERVER_TIMESTAMP,
                        "action_code": "schedule_sleep", # Mã riêng báo hiệu đang ngủ
                        "image_filename": filename,
                        "is_alert": False,       # Tắt báo động
                        "trigger_light": False,  # Tắt đèn
                        "trigger_buzzer": False, # Tắt còi
                        "message": "Ngoài giờ hoạt động"
                    }
                    
                    # CHỈ CẬP NHẬT TRẠNG THÁI MỚI NHẤT (Để ESP32 tắt đèn/còi)
                    device_ref.update({"latest_log": quiet_log})
                    
                    # KHÔNG GHI VÀO COLLECTION 'logs' (Để không làm rác lịch sử)
                    # Và xóa ảnh tạm
                    if os.path.exists(temp_path): os.remove(temp_path)
                    return # Kết thúc hàm tại đây
            # ========================================================

        # --- NẾU TRONG GIỜ HOẠT ĐỘNG THÌ CHẠY TIẾP BÊN DƯỚI ---
        
        s3_client.download_file(S3_BUCKET_NAME, s3_key, temp_path)
        with open(temp_path, "rb") as f:
            b64_img = base64.b64encode(f.read()).decode('utf-8')

        # Gửi cho AI
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"Return only one label: {', '.join(ACTION_LABELS)}"},
                {"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}]}
            ],
            max_tokens=20
        )
        action = response.choices[0].message.content.strip().replace('"','').replace('.','')
        if action not in ACTION_LABELS: action = "unknown_action"

        # Tính toán đèn/còi (Logic cũ)
        trigger_light = False
        trigger_buzzer = False
        is_alert = False
        
        if dev_doc.exists:
            # ... (Logic lấy config master/action settings giữ nguyên như cũ) ...
            general_settings = full_config.get('general', {})
            master_light = general_settings.get('master_light', True)
            master_buzzer = general_settings.get('master_buzzer', True)
            action_settings = full_config.get(action, {})

            if master_light and action_settings.get('enable_light', False):
                trigger_light = True
            if master_buzzer and action_settings.get('enable_buzzer', False):
                trigger_buzzer = True
            if trigger_light or trigger_buzzer:
                is_alert = True

        # Lưu Log đầy đủ (Vào cả Collection và Latest)
        log_data = {
            "timestamp": firestore.SERVER_TIMESTAMP,
            "action_code": action,
            "image_filename": filename,
            "is_alert": is_alert,
            "trigger_light": trigger_light,
            "trigger_buzzer": trigger_buzzer
        }
        device_ref.collection('logs').add(log_data)     # <-- Ghi lịch sử
        device_ref.update({"latest_log": log_data})     # <-- Cập nhật trạng thái
        
        print(f"AI Result [{device_id}]: {action} | Light: {trigger_light} | Buzzer: {trigger_buzzer}")

    except Exception as e:
        print(f"AI Processing Error: {e}")
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)

# ================= API ENDPOINTS =================

# 1. API: Mobile App gọi để bắt đầu chế độ ghép đôi// API 1:
# //{
#     "user_id": "test_user_bang_postman"
# }

#  { "user_id": "test_user_bang_postman", "device_id": "6C:C8:40:34:85:7C" }
@app.route('/api/start-pairing', methods=['POST'])
def start_pairing():
    data = request.json
    user_id = data.get('user_id')
    if not user_id: return jsonify({"error": "missing user_id"}), 400
    db.collection('pairing_queue').document(user_id).set({
        'user_id': user_id,
        'timestamp': firestore.SERVER_TIMESTAMP,
        'status': 'waiting'
    })
    return jsonify({"status": "waiting", "message": "Ready to pair device"}), 200

# 2. API: ESP32 gọi để xác thực (Handshake)
@app.route('/device-handshake', methods=['POST'])
def handshake():
    encrypted_data = request.data.decode('utf-8')
    decrypted_json = decrypt_text(encrypted_data)
    
    if not decrypted_json:
        return jsonify({"status": "error"}), 400

    try:
        info = json.loads(decrypted_json)
        mac = info.get('device_id')
    except:
        return jsonify({"status": "error"}), 400

    device_ref = db.collection('devices').document(mac)
    doc = device_ref.get()
    
    response_data = {}

    if doc.exists:
        # Đã đăng ký -> Trả về cấu hình
        data = doc.to_dict()
        response_data = {
            "status": "authorized",
            "owner": data.get('user_id'),
            "config": data.get('config', {})
        }
    else:
        # Chưa đăng ký -> Tìm trong hàng đợi
        queues = db.collection('pairing_queue').where('status', '==', 'waiting').limit(1).stream()
        found_user = None
        for q in queues:
            found_user = q.to_dict().get('user_id')
            db.collection('pairing_queue').document(found_user).delete() # Xóa khỏi hàng đợi
            break
        
        if found_user:
            # Tạo thiết bị mới
            default_config = {
                "sleeping":      {"enable_light": True,  "enable_buzzer": True},
                "using_phone":   {"enable_light": False, "enable_buzzer": True},
                "using_computer":{"enable_light": False, "enable_buzzer": True},
                "no_person":     {"enable_light": True,  "enable_buzzer": True},
                "general":       {"master_light": True,  "master_buzzer": True},
                "schedule": {"start_time": "08:00", "end_time": "22:00", "enabled": True}
            }
            device_ref.set({
                'mac_address': mac,
                'user_id': found_user,
                'config': default_config,
                'created_at': firestore.SERVER_TIMESTAMP
            })
            response_data = {"status": "registered_success", "config": default_config}
        else:
            response_data = {"status": "unauthorized"}

    # Trả về kết quả mã hóa
    return encrypt_text(json.dumps(response_data))

# 3. API: ESP32 gửi ảnh (Mã hóa)
@app.route('/upload', methods=['POST'])
def upload():
    # Header chứa Device ID để định danh (ESP32 gửi kèm)
    device_id = request.headers.get('Device-ID') 
    
    encrypted_b64 = request.data.decode('utf-8')
    raw_image = decrypt_image(encrypted_b64)
    
    if not raw_image: return 'Decrypt Failed', 400

    # Upload lên S3
    filename = f"img_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=f'{S3_IMAGE_FOLDER}/{filename}', Body=raw_image, ContentType='image/jpeg')
    
    # Chạy AI ngầm
    if device_id:
        threading.Thread(target=process_image_ai, args=(filename, device_id)).start()
    
    return 'Upload OK', 200

# 4. API: ESP32 lấy kết quả hành động mới nhất (Polling)
@app.route('/results', methods=['GET'])
def results():
    device_id = request.args.get('device_id')
    if not device_id: 
        return jsonify({"error": "missing device_id"}), 400
    
    # Lấy dữ liệu từ Firebase
    doc = db.collection('devices').document(device_id).get()
    latest = {}
    config = {}
    if doc.exists:
        data = doc.to_dict()
        latest = data.get('latest_log', {})
        config = data.get('config', {})
        if latest and 'image_filename' in latest:
            latest['image_url'] = create_presigned_url(latest['image_filename'])

    # 2. Lấy danh sách lịch sử (cho History Activity) -> THÊM ĐOẠN NÀY
    history_list = []
    try:
        # Lấy 20 log gần nhất từ sub-collection 'logs'
        logs_ref = db.collection('devices').document(device_id).collection('logs')
        # Sắp xếp theo thời gian giảm dần
        logs_docs = logs_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(20).stream()
        
        for log in logs_docs:
            log_data = log.to_dict()
            # Chuyển timestamp thành chuỗi
            if 'timestamp' in log_data and log_data['timestamp']:
                log_data['timestamp'] = str(log_data['timestamp'])
            
            # Tạo link ảnh S3
            if 'image_filename' in log_data:
                log_data['image_url'] = create_presigned_url(log_data['image_filename'])
                
            history_list.append(log_data)
    except Exception as e:
        print("Lỗi lấy history:", e)

    return jsonify({
        "status": "success",
        "latest_action": latest,
        "current_config": config,
        "history": history_list  # <--- Trả về danh sách này cho Android
    })
    
    return jsonify({"status": "empty", "latest_action": None})

@app.route('/api/admin/all-devices', methods=['GET'])
def get_all_devices():
    try:
        docs = db.collection('devices').stream()
        devices = []
        for doc in docs:
            d = doc.to_dict()
            # Thêm ID của document vào dữ liệu trả về để dễ nhìn
            d['device_id'] = doc.id 
            devices.append(d)
        
        return jsonify({
            "status": "success",
            "count": len(devices),
            "devices": devices
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 6. API: Xem chi tiết thông tin của MỘT thiết bị cụ thể
# URL: http://<IP>:3000/api/device-info/<device_id>
@app.route('/api/device-info/<device_id>', methods=['GET'])
def get_device_info(device_id):
    try:
        # Tìm trong collection 'devices'
        doc_ref = db.collection('devices').document(device_id)
        doc = doc_ref.get()

        if doc.exists:
            data = doc.to_dict()
            
            # Lấy thêm logs (lịch sử hoạt động) của thiết bị này (nếu cần)
            # logs_ref = doc_ref.collection('logs').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(5).stream()
            # logs = [l.to_dict() for l in logs_ref]
            # data['recent_logs'] = logs

            return jsonify({
                "status": "success",
                "device_id": device_id,
                "data": data
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": f"Không tìm thấy thiết bị có ID: {device_id}"
            }), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# ================= API: KIỂM TRA QUYỀN SỞ HỮU & LẤY THÔNG TIN USER =================
# URL: http://<IP>:3000/api/check-ownership
# Method: POST
# Body: { "user_id": "test_user_bang_postman", "device_id": "6C:C8:40:34:85:7C" }

#  {
#    # Body: { "user_id": "test_user_bang_postman", "device_id": "6C:C8:40:34:85:7C" } 

#  }
@app.route('/api/check-ownership', methods=['POST'])
def check_ownership():
    # 1. Lấy dữ liệu từ App gửi lên
    data = request.json
    request_user_id = data.get('user_id')
    request_device_id = data.get('device_id')

    if not request_user_id or not request_device_id:
        return jsonify({"status": "error", "message": "Thiếu user_id hoặc device_id"}), 400

    try:
        # 2. Tìm thiết bị trong Database
        device_ref = db.collection('devices').document(request_device_id)
        device_doc = device_ref.get()

        if not device_doc.exists:
            return jsonify({"status": "error", "message": "Thiết bị không tồn tại"}), 404
        
        # 3. Lấy thông tin chủ sở hữu thực sự của thiết bị
        device_data = device_doc.to_dict()
        real_owner = device_data.get('user_id')

        # 4. SO SÁNH (Logic bạn yêu cầu)
        if real_owner == request_user_id:
            # === TRƯỜNG HỢP KHỚP: ĐƯỢC PHÉP SỬ DỤNG ===
            
            # (Tùy chọn) Lấy thêm thông tin chi tiết user nếu bạn có bảng 'users' riêng
            # user_info = db.collection('users').document(request_user_id).get().to_dict()
            
            return jsonify({
                "status": "allowed",
                "message": "Xác thực thành công. Người dùng có quyền điều khiển.",
                "user_info": {
                    "user_id": request_user_id,
                    "role": "owner",
                    "device_config": device_data.get('config') # Trả về cấu hình để App hiển thị
                }
            }), 200
        else:
            # === TRƯỜNG HỢP KHÔNG KHỚP: TỪ CHỐI ===
            return jsonify({
                "status": "denied",
                "message": "CẢNH BÁO: Thiết bị này thuộc về người khác!",
                "current_owner": "Ẩn danh" # Không nên trả về ID người khác vì bảo mật
            }), 403

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
# //   "status": "allowed",
#                 "message": "Xác thực thành công. Người dùng có quyền điều khiển.",
#                 "user_info": {
#                    
#                     "user_id": request_user_id,
#                     "role": "owner",
#                     "device_config": device_data.get('config') # Trả về cấu hình để App hiển thị
#                 }
# Neu message =="Xác thực thành công. Người dùng có quyền điều khiển.", -> main
# Neu message ==CẢNH BÁO: Thiết bị này thuộc về người khác!",, -> xác thực


# API: Lấy danh sách thiết bị của User (Để App quyết định vào Main hay Pairing)
@app.route('/api/get-my-devices', methods=['POST'])
def get_my_devices():
    user_id = request.json.get('user_id')
    
    if not user_id:
        return jsonify({"status": "error", "message": "Missing user_id"}), 400

    try:
        # Tìm tất cả thiết bị mà user_id này đứng tên
        docs = db.collection('devices').where('user_id', '==', user_id).stream()
        
        my_devices = []
        for doc in docs:
            d = doc.to_dict()
            # Chỉ lấy những thông tin cần thiết trả về cho App
            my_devices.append({
                "device_id": doc.id, 
                "config": d.get('config'),
                "created_at": d.get('created_at')
            })
            
        return jsonify({
            "status": "success", 
            "count": len(my_devices),
            "devices": my_devices
        }), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
    # API: Lấy cấu hình thiết bị
@app.route('/get-settings', methods=['GET'])
def get_settings():
    device_id = request.args.get('device_id')
    if not device_id: 
        return jsonify({"status": "error", "message": "missing device_id"}), 400

    try:
        doc = db.collection('devices').document(device_id).get()
        if doc.exists:
            data = doc.to_dict()
            config = data.get('config', {})
            return jsonify({"status": "success", "config": config}), 200
        else:
            return jsonify({"status": "error", "message": "Device not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
    
# API: Cập nhật cấu hình (Chi tiết từng nút)
# @app.route('/update-settings', methods=['POST'])
# def update_settings():
#     try:
#         data = request.json
#         device_id = data.get('device_id')
#         action = data.get('action')       # VD: "sleeping"
#         target = data.get('target')       # VD: "enable_light"
#         enabled = data.get('enabled')     # True/False

#         # Kiểm tra dữ liệu đầu vào
#         if not all([device_id, action, target]) or enabled is None:
#             return jsonify({"status": "error", "message": "Thiếu thông tin (device_id, action, target, enabled)"}), 400

#         # Kiểm tra xem thiết bị có tồn tại không
#         device_ref = db.collection('devices').document(device_id)
#         if not device_ref.get().exists:
#             return jsonify({"status": "error", "message": "Device not found"}), 404
        
#         # Tạo key để update theo kiểu 'config.sleeping.enable_light'
#         # Firestore hỗ trợ update kiểu nested này rất tiện
#         update_key = f'config.{action}.{target}'
        
#         device_ref.update({
#             update_key: enabled
#         })
        
#         print(f"Updated setting: Device {device_id} | {update_key} = {enabled}")
#         return jsonify({"status": "success", "updated": update_key, "value": enabled}), 200
        
#     except Exception as e:
#         print(f"Error updating settings: {e}")
#         return jsonify({"status": "error", "message": str(e)}), 500

# API: Cập nhật cấu hình (Đa năng: Hỗ trợ cả Boolean và String)
@app.route('/update-settings', methods=['POST'])
def update_settings():
    try:
        data = request.json
        device_id = data.get('device_id')
        action = data.get('action')       # VD: "sleeping" hoặc "schedule"
        target = data.get('target')       # VD: "enable_light" hoặc "start_time"
        
        # --- [SỬA ĐỔI QUAN TRỌNG] ---
        # 1. Ưu tiên lấy biến 'value' (dùng cho giờ giấc string)
        value = data.get('value')
        
        # 2. Nếu không có 'value', thử lấy 'enabled' (dùng cho switch true/false cũ)
        if value is None:
            value = data.get('enabled')

        # 3. Kiểm tra dữ liệu đầu vào
        # Lưu ý: value có thể là False (boolean), nên không check "if not value"
        if not all([device_id, action, target]) or value is None:
            return jsonify({"status": "error", "message": "Thiếu thông tin (device_id, action, target, value)"}), 400

        # Kiểm tra thiết bị
        device_ref = db.collection('devices').document(device_id)
        if not device_ref.get().exists:
            return jsonify({"status": "error", "message": "Device not found"}), 404
        
        # Tạo key nested (VD: config.schedule.start_time)
        update_key = f'config.{action}.{target}'
        
        # Update lên Firestore
        device_ref.update({
            update_key: value
        })
        
        print(f"Updated: {device_id} | {update_key} = {value}")
        return jsonify({"status": "success", "updated": update_key, "value": value}), 200
        
    except Exception as e:
        print(f"Error updating settings: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    

if __name__ == '__main__':
    print("SERVER STARTED - FIREBASE & AES ENABLED")
    app.run(host='0.0.0.0', port=3000, debug=True)