import os
import time
from ultralytics import YOLO


ACTION_LABELS = [
    "writing", 
    "reading", 
    "sleeping", 
    "using_computer", 
    "using_phone", 
    "no_person", 
    "other_action"
]

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

try:
    MODEL_PATH = 'best.pt'
    model = YOLO(MODEL_PATH) 
    print(f"✅ Đã tải mô hình YOLO từ '{MODEL_PATH}'.")
except ImportError:
    print("⚠️ LỖI: Cần cài đặt thư viện 'ultralytics': pip install ultralytics")
    exit()
except Exception as e:
    print(f"⚠️ LỖI: Không thể tải mô hình từ '{MODEL_PATH}'. Lỗi: {e}")
    exit()


def classify_image_and_check_alert(image_path: str):
    print(f"\n[AI] Đang phân tích: {os.path.basename(image_path)}")
    start = time.time()
    label = "unknown_action"
    alert_message = ""
    try:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"File ảnh không tồn tại: {image_path}")
        results = model(image_path, verbose=False, device='cpu') 
        result = results[0] 
        if result.probs is not None:
            top_index = result.probs.top1 
            predicted_label = model.names[top_index]
        elif len(result.boxes) > 0:
            top_box_index = result.boxes.conf.argmax().item()
            top_class_index = result.boxes.cls[top_box_index].item()
            predicted_label = model.names[int(top_class_index)]
        else:
            predicted_label = "no_person"    
        if predicted_label in ACTION_LABELS:
            label = predicted_label
        else:
            label = "other_action" 
        if label in ALERT_ACTIONS:
            alert_message = ALERT_ACTIONS[label]
        elif label in NORMAL_ACTIONS:
            alert_message = NORMAL_ACTIONS[label]
        elif label == "unknown_action":
             alert_message = NORMAL_ACTIONS["unknown_action"]
        else:
            alert_message = f"Hành động '{label}' được phát hiện."
        elapsed = time.time() - start
        return (label, alert_message, elapsed)
    except Exception as e:
        elapsed = time.time() - start
        print(f"[LỖI AI] Lỗi xử lý: {e}")
        return None, None, elapsed