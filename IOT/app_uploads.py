import os
import base64
import time
import threading
from datetime import datetime
from flask import Flask, request, send_from_directory, jsonify
from openai import OpenAI
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
OUTPUT_FILE = os.path.join(BASE_DIR, 'results.txt')
MODEL_PATH= os.path.join(BASE_DIR, 'best_v2.pt')
load_dotenv(os.path.join(BASE_DIR, '.env'))
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("Không tìm thấy OPENAI_API_KEY trong .env")

client = OpenAI(api_key=api_key)

app = Flask(__name__)
PORT = 3000

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

def classify_image(image_path):
    base64_img = encode_image(image_path)
    print(f"✅ Đã tải mô hình YOLO từ '{MODEL_PATH}'.")
    print(f"\n[AI] Đang phân tích: {os.path.basename(image_path)}")
    system_prompt = f"Chỉ trả về 1 nhãn từ: {', '.join(ACTION_LABELS)}. Không giải thích."

    print(f"[Model] Đang phân tích: {os.path.basename(image_path)}")
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
        return (label if label in ACTION_LABELS else "unknown_action"), elapsed
    except Exception as e:
        print(f"[LỖI AI] {e}")
        return None, (time.time() - start)

def save_result(filename, action, elapsed):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} | {filename}: {action}\n"
    with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
        f.write(line)
    print(f"[HOÀN TẤT] {line.strip()}")

def process_new_image(filepath):
    filename = os.path.basename(filepath)
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            if any(filename in line for line in f):
                return 
    action, elapsed = classify_image(filepath)
    if action: 
        save_result(filename, action, elapsed)


@app.route('/upload', methods=['POST'])
def upload():
    if not request.data: return 'No data', 400
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    filename = f"img_{timestamp}.jpg"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, 'wb') as f:
        f.write(request.data)
    print(f"Nhận ảnh: {filename}")
    threading.Thread(target=process_new_image, args=(filepath,), daemon=True).start()
    return '', 200

@app.route('/uploads/<filename>')
def get_image(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@app.route('/update-settings', methods=['POST'])
def update_settings():
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
    if not os.path.exists(OUTPUT_FILE):
        return jsonify({"status": "empty", "latest_action": None, "history": []}), 200

    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f if l.strip()]

    if not lines:
         return jsonify({"status": "empty", "latest_action": None, "history": []}), 200

    data_list = []
    recent_lines = lines[-50:]
    base_url = request.host_url

    for line in recent_lines:
        try:
            if '|' not in line or ':' not in line: continue
            ts_part, content_part = line.split('|', 1)
            timestamp = ts_part.strip()
            filename_part, action_raw = content_part.split(':', 1)
            filename = filename_part.strip()

            action_code = action_raw.split('(')[0].strip()
            
            should_alert = False
            

            if action_code in ALERT_ACTIONS:

                if ALARM_CONFIG.get(action_code, True) == True:
                    should_alert = True

            display_message = ALERT_ACTIONS.get(action_code, NORMAL_ACTIONS.get(action_code, action_code))

            full_image_url = f"{base_url}uploads/{filename}"
            print(f"Hành động của {filename} là {action_code}, cảnh báo: {should_alert}")
            data_list.append({
                "timestamp": timestamp,
                "image_name": filename,
                "image_url": full_image_url,
                "action_code": action_code,
                "message": display_message,
                "is_alert": should_alert  
            })
        except Exception:
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
