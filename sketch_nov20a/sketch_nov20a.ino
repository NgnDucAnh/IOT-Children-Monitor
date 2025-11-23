#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h> // Version 7.x.x

// ================= CẤU HÌNH WIFI & SERVER =================
const char* ssid = "Dank";
const char* password = "12345678";
const char* uploadURL = "http://192.168.131.38:3000/upload";   
const char* resultsURL = "http://192.168.131.38:3000/results"; 

// ================= CẤU HÌNH PHẦN CỨNG =================
#define BUZZER_PIN 2            // Chân kết nối loa
#define FLASH_LED_PIN 4         // Đèn Flash có sẵn trên ESP32-CAM
#define UPLOAD_INTERVAL 5000    // 5 giây xử lý 1 lần

// Hành động cần cảnh báo
const char* ALERT_ACTIONS[] = {"using_phone", "using_computer", "sleeping", "no_person"};
const int ALERT_COUNT = 4;

// ================= CAMERA PINS (OV2640 - AI THINKER) =================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define D7_GPIO_NUM       35
#define D6_GPIO_NUM       34
#define D5_GPIO_NUM       39
#define D4_GPIO_NUM       36
#define D3_GPIO_NUM       21
#define D2_GPIO_NUM       19
#define D1_GPIO_NUM       18
#define D0_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// ================= BIẾN TOÀN CỤC =================
unsigned long lastUploadTime = 0;
bool wifiConnected = false;

// ================= HÀM CẢNH BÁO (LOA + ĐÈN) =================
void triggerAlert() {
  Serial.println("!!! CẢNH BÁO: PHÁT HIỆN HÀNH VI !!!");
  
  // Nháy 5 lần cho gây chú ý
  for (int i = 0; i < 5; i++) {
    digitalWrite(BUZZER_PIN, HIGH);    // Bật Loa
    digitalWrite(FLASH_LED_PIN, HIGH); // Bật Đèn Flash
    delay(200); // Kêu/Sáng trong 0.2s
    
    digitalWrite(BUZZER_PIN, LOW);     // Tắt Loa
    digitalWrite(FLASH_LED_PIN, LOW);  // Tắt Đèn Flash
    delay(200); // Nghỉ 0.2s
  }
}

// ================= HÀM KIỂM TRA DANH SÁCH CẤM =================
bool isAlertAction(const char* action) {
  if (!action) return false;
  for (int i = 0; i < ALERT_COUNT; i++) {
    if (strcmp(action, ALERT_ACTIONS[i]) == 0) {
      return true;
    }
  }
  return false;
}

// ================= SETUP =================
void setup() {
  Serial.begin(115200);
  
  // Cấu hình chân ra (Output)
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(FLASH_LED_PIN, OUTPUT);
  
  // Trạng thái ban đầu: Tắt hết
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(FLASH_LED_PIN, LOW);

  Serial.println("\nKhởi động ESP32-CAM...");

  // === KẾT NỐI WIFI ===
  WiFi.begin(ssid, password);
  Serial.print("Đang kết nối WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi kết nối thành công!");
  Serial.print("IP: "); Serial.println(WiFi.localIP());
  wifiConnected = true;

  // === KHỞI TẠO CAMERA ===
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = D0_GPIO_NUM;
  config.pin_d1 = D1_GPIO_NUM;
  config.pin_d2 = D2_GPIO_NUM;
  config.pin_d3 = D3_GPIO_NUM;
  config.pin_d4 = D4_GPIO_NUM;
  config.pin_d5 = D5_GPIO_NUM;
  config.pin_d6 = D6_GPIO_NUM;
  config.pin_d7 = D7_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  
  // Nếu chụp ảnh bị lỗi hoặc sọc, thử giảm kích thước xuống QVGA
  config.frame_size = FRAMESIZE_VGA; 
  config.jpeg_quality = 12;
  config.fb_count = 1;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera lỗi khởi tạo: 0x%x\n", err);
    while (1) delay(1000);
  }
  Serial.println("Camera sẵn sàng!");
  Serial.println("Hệ thống giám sát bắt đầu...");
}

// ================= LOOP =================
void loop() {
  // 1. Kiểm tra WiFi (Tự động kết nối lại nếu rớt mạng)
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Mất kết nối! Đang thử kết nối lại...");
    WiFi.disconnect();
    WiFi.reconnect();
    delay(5000);
    return;
  }

  // 2. Kiểm tra thời gian (Chụp mỗi 1 phút - 60000ms)
  unsigned long now = millis();
  if (now - lastUploadTime < UPLOAD_INTERVAL) {
    delay(100); // Nghỉ nhẹ để CPU mát, đồng thời giữ Stream video (nếu có)
    return;
  }
  lastUploadTime = now;

  // === BƯỚC 1: CHỤP ẢNH ===
  Serial.println("--- Bắt đầu chu trình mới ---");
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Lỗi: Không chụp được ảnh");
    return;
  }

  // === BƯỚC 2: GỬI ẢNH ===
  HTTPClient http;
  http.begin(uploadURL);
  http.addHeader("Content-Type", "image/jpeg");
  
  // Tăng timeout lên 10s để tránh lỗi khi gửi sau thời gian dài
  http.setTimeout(10000); 
  
  int httpCode = http.POST(fb->buf, fb->len);
  esp_camera_fb_return(fb); // Giải phóng bộ nhớ camera ngay

  if (httpCode == 200) {
    Serial.println("Đã gửi ảnh lên Server.");
  } else {
    Serial.printf("Gửi ảnh thất bại. Lỗi: %d\n", httpCode);
    http.end();
    return; // Nếu gửi lỗi thì thôi không cần hỏi kết quả nữa
  }
  http.end();

  // === BƯỚC 3: ĐỢI AI XỬ LÝ ===
  // Server Python xử lý rất nhanh, nhưng nên đợi xíu để file được ghi xong
  delay(2000);

  // === BƯỚC 4: LẤY KẾT QUẢ VÀ XỬ LÝ CẢNH BÁO DỰA TRÊN SERVER ===
  HTTPClient http2;
  http2.begin(resultsURL);
  int code2 = http2.GET();
  
  if (code2 == 200) {
    String payload = http2.getString();
    Serial.print("JSON nhận được: ");
    Serial.println(payload); 

    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, payload);

    if (!error) {
      // Truy cập vào object "latest_action"
      JsonObject latest = doc["latest_action"];
      
      const char* action = latest["action_code"];
      
      // --- SỬA ĐỔI QUAN TRỌNG TẠI ĐÂY ---
      // Đọc cờ báo động do Server quyết định (dựa trên cấu hình từ App)
      bool serverSaysAlert = latest["is_alert"]; 

      Serial.print(">>> KẾT QUẢ: ");
      if (action) {
        Serial.print(action);
        Serial.print(" | Cần báo động: ");
        Serial.println(serverSaysAlert ? "CÓ" : "KHÔNG");

        // Chỉ hú còi khi Server bảo True
        if (serverSaysAlert == true) {
           triggerAlert(); 
        }
      } else {
        Serial.println("Không có hành động mới.");
      }
      // -----------------------------------

    } else {
      Serial.print("Lỗi parse JSON: ");
      Serial.println(error.c_str());
    }
  } else {
    Serial.printf("Lỗi lấy kết quả AI: %d\n", code2);
  }
  http2.end();
  
  Serial.println("--- Kết thúc chu trình ---");
}