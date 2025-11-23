import os
import base64
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
  raise ValueError("Không tìm thấy OPENAI_API_KEY. Vui lòng kiểm tra tệp .env")

client = OpenAI(api_key=api_key)

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')
      
def classify_student_action(image_path):
    
    base64_image = encode_image_to_base64(image_path)
    
    action_labels = ["writing", "reading", "sleeping", "using_computer", "using_phone", "no_person"]
    

    system_prompt = f"""
    Bạn là một hệ thống AI giám sát hành vi của học sinh. 
    Nhiệm vụ của bạn là phân tích hình ảnh được cung cấp và chỉ trả về MỘT nhãn duy nhất 
    mô tả hành động chính của học sinh trong hình.
    
    Các nhãn hợp lệ là: {', '.join(action_labels)}.

    Nếu không có người trong ảnh, hãy trả về 'no_person'.
    Chỉ trả lời bằng nhãn, không thêm bất kỳ văn bản giải thích nào.
    """

    print(f"Đang gửi ảnh '{image_path}' để phân tích...")
    start_time = time.time()
    try:
        response = client.chat.completions.create(
            model="gpt-4o", 
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Phân tích hình ảnh này và cho tôi biết hành động."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=50 
        )
        end_time = time.time()
        elapsed_time = end_time - start_time
        classification = response.choices[0].message.content.strip()
        cleaned_classification = classification.replace('"', '').replace('.', '')
        
        if cleaned_classification in action_labels:
            return cleaned_classification, elapsed_time
        else:
            print(f"  Lỗi: AI trả về nhãn không mong muốn: '{classification}'")
            return "unknown_action", elapsed_time

    except Exception as e:
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        print(f"  Đã xảy ra lỗi khi gọi API cho ảnh {os.path.basename(image_path)}: {e}")
        return None, elapsed_time

if __name__ == "__main__":
    
    input_folder = "image_test"
    output_folder = "output_test"
    output_file_path = os.path.join(output_folder, "results.txt")
    
    valid_extensions = ('.jpg', '.jpeg', '.png')
    
    total_time = 0
    image_count = 0
    
    print(f"--- Bắt đầu xử lý hàng loạt thư mục '{input_folder}' ---")
    
    with open(output_file_path, 'w', encoding='utf-8') as result_file:
        
        for filename in sorted(os.listdir(input_folder)):
            
            if filename.lower().endswith(valid_extensions):
                
                image_path = os.path.join(input_folder, filename)
                
                action, time_taken = classify_student_action(image_path)
                
                if action:
                    print(f"  -> Kết quả: {action} (Thời gian: {time_taken:.2f} giây)")
                    result_file.write(f"{filename}: {action} (Thời gian: {time_taken:.2f} giây)\n")
                    total_time += time_taken
                    image_count += 1
                else:
                    print(f"  -> Bỏ qua tệp do lỗi.")
            
            else:
                print(f"Bỏ qua tệp không phải ảnh: {filename}")

    print(f"--- Xử lý hoàn tất! ---")
    print(f"Kết quả đã được lưu tại: {output_file_path}")
    
    if image_count > 0:
        average_time = total_time / image_count
        print(f"Đã xử lý {image_count} ảnh.")
        print(f"Tổng thời gian API: {total_time:.2f} giây.")
        print(f"Thời gian trung bình mỗi ảnh: {average_time:.2f} giây.")