import os
import base64
import time
import threading
from datetime import datetime
from flask import Flask, request, send_from_directory, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
# OUTPUT_FILE = os.path.join(BASE_DIR, 'results.txt')

MODEL_PATH= os.path.join(BASE_DIR, 'best_v2.pt')
load_dotenv(os.path.join(BASE_DIR, '.env'))
api_key = os.getenv("OPENAI_API_KEY")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_RESULTS_KEY = os.getenv("S3_RESULTS_KEY") 
AWS_REGION = os.getenv("AWS_REGION")

IOT_BASE_FOLDER = 'IOT'
S3_IMAGE_FOLDER = f'{IOT_BASE_FOLDER}/images' 
S3_RESULTS_KEY = f'{IOT_BASE_FOLDER}/history.txt'

if not api_key or not S3_BUCKET_NAME:
    raise ValueError("Thiếu biến môi trường quan trọng (API Key/S3 Config)")

client = OpenAI(api_key=api_key)

app = Flask(__name__)
PORT = 3000

TEMP_DIR = os.path.join(BASE_DIR, 'temp_ai')
os.makedirs(TEMP_DIR, exist_ok=True)

try:
    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=AWS_REGION
    )
except ClientError as e:
    print(f"[LỖI S3] Lỗi khởi tạo Client: {e}")

ACTION_LABELS = ["writing", "reading", "sleeping", "using_computer", "using_phone", "no_person", "other_action"]

ALERT_ACTIONS = {
    "sleeping": "Cảnh báo: Học sinh đang ngủ gật!",
    "using_phone": "Cảnh báo: Học sinh đang dùng điện thoại!",
    "no_person": "Cảnh báo: Học sinh đã rời khỏi vị trí!",
    "using_computer": "Cảnh báo: Học sinh đang dùng máy tính"
}

NORMAL_ACTIONS = {
    "writing": "Đang chép bài",
    "reading": "Đang đọc sách",
    "unknown_action": "Hành động lạ!",
    "other_action": "Hoạt động khác"
}

ALARM_CONFIG = {
    "sleeping": True,
    "using_phone": True,
    "using_computer": True,
    "no_person": True
}


if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

def create_presigned_url(object_name, expiration=3600):
    """Tạo URL tạm thời có thời hạn cho phép tải ảnh từ S3"""
    image_s3_key = f'{S3_IMAGE_FOLDER}/{object_name}' 
    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': S3_BUCKET_NAME,
                                                            'Key': image_s3_key}, 
                                                    ExpiresIn=expiration)
    except ClientError as e:
        print(f"[LỖI S3] Không thể tạo URL cho {object_name}: {e}")
        return None
    return response

def get_s3_results_content():
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=S3_RESULTS_KEY)
        content = response['Body'].read().decode('utf-8')
        return content
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return "" 
        else:
            print(f"[LỖI S3 TẢI RESULTS] {e}")
            raise

def save_result_to_s3(filename, action, elapsed):
    """Ghi thêm dòng kết quả vào file history trên S3 (Read-Modify-Write)"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_line = f"{timestamp} | {filename}: {action}\n"
    
    try:
        existing_content = get_s3_results_content()
        
        updated_content = existing_content + new_line
        
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=S3_RESULTS_KEY,
            Body=updated_content.encode('utf-8'),
            ContentType='text/plain'
        )
        print(f"[S3 - HOÀN TẤT] Đã ghi kết quả cho {filename} lên S3.")
    except Exception as e:
        print(f"[LỖI S3 GHI] Không thể ghi results.txt: {e}")

def classify_image_from_s3(filename):
    """Tải ảnh tạm thời từ S3, phân loại bằng AI và xóa ảnh tạm thời"""
    temp_filepath = os.path.join(TEMP_DIR, filename) 
    
    image_s3_key = f'{S3_IMAGE_FOLDER}/{filename}'
    try:
        s3_client.download_file(S3_BUCKET_NAME, image_s3_key, temp_filepath) 
        print(f"[AI] Đã tải ảnh tạm thời từ {image_s3_key}: {filename}")
    except ClientError as e:
        print(f"[LỖI S3 TẢI] Không thể tải ảnh {image_s3_key}: {e}")
        return None, 0
    
    base64_img = encode_image(temp_filepath)
    # print(f"✅ Đã tải mô hình YOLO từ '{MODEL_PATH}'.") 
    print(f"\n[AI] Đang phân tích: {filename}")
    system_prompt = f"Chỉ trả về 1 nhãn từ: {', '.join(ACTION_LABELS)}. Không giải thích."
    
    start = time.time()
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": "Hành động học sinh?"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                ]}
            ],
            max_tokens=50
        )
        elapsed = time.time() - start
        label = response.choices[0].message.content.strip().replace('"', '').replace('.', '')
        
        os.remove(temp_filepath)
        print(f"[AI] Đã xóa ảnh tạm thời: {filename}")
        
        return (label if label in ACTION_LABELS else "unknown_action"), elapsed
    except Exception as e:
        print(f"[LỖI AI] {e}")
        if os.path.exists(temp_filepath):
             os.remove(temp_filepath)
        return None, (time.time() - start)

def process_new_image(filename):
    action, elapsed = classify_image_from_s3(filename)
    if action: 
        save_result_to_s3(filename, action, elapsed)


@app.route('/upload', methods=['POST'])
def upload():
    """Nhận ảnh từ ESP32 và TẢI LÊN S3 vào IOT/uploads"""
    if not request.data: return 'No data', 400
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    filename = f"img_{timestamp}.jpg"
    
    image_s3_key = f'{S3_IMAGE_FOLDER}/{filename}'

    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=image_s3_key, \
            Body=request.data,
            ContentType='image/jpeg'
        )
        print(f"Nhận và tải lên S3: {image_s3_key}")
        
        threading.Thread(target=process_new_image, args=(filename,), daemon=True).start()
        
        return '', 200
        
    except ClientError as e:
        print(f"[LỖI S3] Không thể tải ảnh lên S3: {e}")
        return 'S3 upload failed', 500

@app.route('/upload', methods=['POST'])
def upload():
    """ENDPOINT MỚI: Nhận ảnh từ ESP32 và TẢI LÊN S3"""
    if not request.data: return 'No data', 400
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    filename = f"img_{timestamp}.jpg"
    
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=filename, 
            Body=request.data,
            ContentType='image/jpeg'
        )
        print(f"Nhận và tải lên S3: {filename}")
        
        threading.Thread(target=process_new_image, args=(filename,), daemon=True).start()
        
        return '', 200
        
    except ClientError as e:
        print(f"[LỖI S3] Không thể tải ảnh lên S3: {e}")
        return 'S3 upload failed', 500


@app.route('/update-settings', methods=['POST'])
def update_settings():
    """ENDPOINT CẤU HÌNH (GIỮ NGUYÊN)"""
    try:
        data = request.json
        action = data.get('action') 
        enabled = data.get('enabled')
        
        if action in ALARM_CONFIG:
            ALARM_CONFIG[action] = bool(enabled)
            print(f"[SETTINGS] Đã cập nhật: {action} -> {ALARM_CONFIG[action]}")
            return jsonify({"status": "success", "config": ALARM_CONFIG}), 200
        return jsonify({"status": "error", "message": "Invalid action"}), 400
    except Exception as e:
        print(e)
        return jsonify({"status": "error"}), 500


@app.route('/results', methods=['GET'])
def results():
    """ENDPOINT MỚI: Trả về LỊCH SỬ LOG từ S3 và PRE-SIGNED URL cho ảnh"""
    
    try:
        raw_content = get_s3_results_content()
    except Exception:
        return jsonify({"status": "empty", "latest_action": None, "history": []}), 200

    lines = [l.strip() for l in raw_content.split('\n') if l.strip()]

    if not lines:
        return jsonify({"status": "empty", "latest_action": None, "history": []}), 200

    data_list = []
    recent_lines = lines[-50:] 

    for line in recent_lines:
        try:
            if '|' not in line or ':' not in line: continue
            ts_part, content_part = line.split('|', 1)
            timestamp = ts_part.strip()
            filename_part, action_raw = content_part.split(':', 1)
            filename = filename_part.strip()

            action_code = action_raw.split('(')[0].strip()
            
            should_alert = action_code in ALERT_ACTIONS and ALARM_CONFIG.get(action_code, True)
            display_message = ALERT_ACTIONS.get(action_code, NORMAL_ACTIONS.get(action_code, action_code))

            full_image_url = create_presigned_url(filename, expiration=3600)
            
            data_list.append({
                "timestamp": timestamp,
                "image_name": filename,
                "image_url": full_image_url, 
                "action_code": action_code,
                "message": display_message,
                "is_alert": should_alert 
            })
        except Exception as e:
            continue

    data_list.reverse()
    
    return jsonify({
        "status": "success",
        "latest_action": data_list[0] if data_list else None,
        "history": data_list
    }), 200

if __name__ == '__main__':
    print(f"SERVER ĐANG CHẠY TẠI CỔNG {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
