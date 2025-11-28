#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h> // Yêu cầu bản 7.x
#include "mbedtls/aes.h"
#include "mbedtls/base64.h"

// ================= CẤU HÌNH NGƯỜI DÙNG =================
const char* ssid = "vinhnv2";
const char* password = "nphnda215212@";
String serverIP = "192.168.1.67"; // Thay IP máy tính chạy Python
int serverPort = 3000;

// ================= CẤU HÌNH PHẦN CỨNG =================
#define BUZZER_PIN 2
#define FLASH_LED_PIN 4
#define UPLOAD_INTERVAL 20000 // 60 giây

// ================= CẤU HÌNH MÃ HÓA (AES-128) =================
// Phải khớp hoàn toàn với Python
unsigned char key[16] = {0x1A, 0x2B, 0x3C, 0x4D, 0x5E, 0x6F, 0x70, 0x81, 0x92, 0xA3, 0xB4, 0xC5, 0xD6, 0xE7, 0xF8, 0x09};
unsigned char iv[16]  = {0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF};

// ================= CAMERA PINS =================
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
String deviceMAC = "";
bool isAuthorized = false; // Cờ kiểm tra quyền
unsigned long lastUploadTime = 0;

// ================= HÀM MÃ HÓA / GIẢI MÃ =================

// Mã hóa chuỗi (JSON)
String encryptText(String plainText) {
  int len = plainText.length();
  int n_blocks = len / 16 + 1;
  int totalLen = n_blocks * 16;
  int n_padding = 16 - (len % 16);

  unsigned char input[totalLen];
  plainText.getBytes(input, len + 1);
  for (int i = len; i < totalLen; i++) input[i] = n_padding; // PKCS7 Padding

  unsigned char output[totalLen];
  unsigned char iv_copy[16];
  memcpy(iv_copy, iv, 16); // IV bị thay đổi sau khi dùng nên cần copy

  mbedtls_aes_context aes;
  mbedtls_aes_init(&aes);
  mbedtls_aes_setkey_enc(&aes, key, 128);
  mbedtls_aes_crypt_cbc(&aes, MBEDTLS_AES_ENCRYPT, totalLen, iv_copy, input, output);
  mbedtls_aes_free(&aes);

  size_t olen;
  unsigned char b64[totalLen * 2];
  mbedtls_base64_encode(b64, sizeof(b64), &olen, output, totalLen);
  return String((char*)b64);
}

// Mã hóa Binary (Ảnh)
String encryptImage(uint8_t* data, size_t len) {
  int n_blocks = len / 16 + 1;
  int totalLen = n_blocks * 16;
  int n_padding = 16 - (len % 16);

  uint8_t* input = (uint8_t*)ps_malloc(totalLen);
  if(!input) return "";
  memcpy(input, data, len);
  for(int i=len; i<totalLen; i++) input[i] = n_padding;

  uint8_t* output = (uint8_t*)ps_malloc(totalLen);
  unsigned char iv_copy[16];
  memcpy(iv_copy, iv, 16);

  mbedtls_aes_context aes;
  mbedtls_aes_init(&aes);
  mbedtls_aes_setkey_enc(&aes, key, 128);
  mbedtls_aes_crypt_cbc(&aes, MBEDTLS_AES_ENCRYPT, totalLen, iv_copy, input, output);
  mbedtls_aes_free(&aes);
  
  // Base64 encode
  size_t olen;
  size_t b64_len = totalLen * 4 / 3 + 4;
  uint8_t* b64 = (uint8_t*)ps_malloc(b64_len);
  mbedtls_base64_encode(b64, b64_len, &olen, output, totalLen);
  
  String result = String((char*)b64);
  free(input); free(output); free(b64);
  return result;
}

// Giải mã chuỗi (Nhận từ Server)
String decryptText(String encryptedB64) {
  size_t len = encryptedB64.length();
  size_t olen;
  unsigned char* decoded = (unsigned char*)malloc(len);
  mbedtls_base64_decode(decoded, len, &olen, (const unsigned char*)encryptedB64.c_str(), len);

  unsigned char* decrypted = (unsigned char*)malloc(olen);
  unsigned char iv_copy[16];
  memcpy(iv_copy, iv, 16);

  mbedtls_aes_context aes;
  mbedtls_aes_init(&aes);
  mbedtls_aes_setkey_dec(&aes, key, 128);
  mbedtls_aes_crypt_cbc(&aes, MBEDTLS_AES_DECRYPT, olen, iv_copy, decoded, decrypted);
  mbedtls_aes_free(&aes);

  // Unpad
  int pad = decrypted[olen - 1];
  if(pad > 0 && pad <= 16) decrypted[olen - pad] = '\0';
  else decrypted[olen] = '\0';

  String res = String((char*)decrypted);
  free(decoded); free(decrypted);
  return res;
}

// ================= HÀM XỬ LÝ CHÍNH =================

void triggerAlert() {
  Serial.println("!!! CẢNH BÁO !!!");
  for (int i = 0; i < 3; i++) {
    digitalWrite(BUZZER_PIN, HIGH);
    digitalWrite(FLASH_LED_PIN, HIGH);
    delay(200);
    digitalWrite(BUZZER_PIN, LOW);
    digitalWrite(FLASH_LED_PIN, LOW);
    delay(200);
  }
}

void triggerBuzzer() {
  for (int i = 0; i < 3; i++) {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(200);
    digitalWrite(BUZZER_PIN, LOW);
    delay(200);
  }
}

// --- HÀM ĐIỀU KHIỂN ĐÈN (FLASH) ---
void triggerFlash() {
  for (int i = 0; i < 3; i++) {
    digitalWrite(FLASH_LED_PIN, HIGH);
    delay(200);
    digitalWrite(FLASH_LED_PIN, LOW);
    delay(200);
  }
}

// Gửi yêu cầu Handshake
void performHandshake() {
  if (WiFi.status() != WL_CONNECTED) return;
  
  HTTPClient http;
  String url = "http://" + serverIP + ":" + String(serverPort) + "/device-handshake";
  http.begin(url);
  
  // Tạo JSON chứa Device ID
  JsonDocument doc;
  doc["device_id"] = deviceMAC;
  String jsonPayload;
  serializeJson(doc, jsonPayload);

  // Gửi mã hóa
  String encrypted = encryptText(jsonPayload);
  int code = http.POST(encrypted);

  if (code == 200) {
    String responseEnc = http.getString();
    String responseJson = decryptText(responseEnc);
    Serial.println("Handshake Resp: " + responseJson);

    JsonDocument respDoc;
    deserializeJson(respDoc, responseJson);
    const char* status = respDoc["status"];
    
    if (strcmp(status, "authorized") == 0 || strcmp(status, "registered_success") == 0) {
      isAuthorized = true;
      Serial.println(">>> ĐÃ ĐƯỢC CẤP QUYỀN TRUY CẬP");
    } else {
      isAuthorized = false;
      Serial.println(">>> BỊ TỪ CHỐI. Vui lòng Pairing từ App.");
    }
  } else {
    Serial.printf("Lỗi Handshake: %d\n", code);
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(FLASH_LED_PIN, OUTPUT);

  // Kết nối WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected!");
  deviceMAC = WiFi.macAddress();
  Serial.println("Device MAC: " + deviceMAC);

  // Khởi tạo Camera
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
  config.frame_size = FRAMESIZE_VGA;
  config.jpeg_quality = 12;
  config.fb_count = 1;
  esp_camera_init(&config);

  // Thử Handshake ngay khi khởi động
  performHandshake();
}

// void loop() {
//   // 1. Kiểm tra kết nối
//   if (WiFi.status() != WL_CONNECTED) {
//     WiFi.disconnect(); WiFi.reconnect(); return;
//   }

//   // 2. Nếu chưa được cấp quyền, thử lại mỗi 10s
//   if (!isAuthorized) {
//     delay(10000);
//     performHandshake();
//     return;
//   }

//   // 3. Chu trình Upload
//   unsigned long now = millis();
//   if (now - lastUploadTime < UPLOAD_INTERVAL) return;
//   lastUploadTime = now;

//   camera_fb_t * fb = esp_camera_fb_get();
//   if (!fb) return;

//   // Mã hóa ảnh
//   String encryptedImg = encryptImage(fb->buf, fb->len);
//   esp_camera_fb_return(fb);

//   // Gửi ảnh
//   HTTPClient http;
//   String uploadUrl = "http://" + serverIP + ":" + String(serverPort) + "/upload";
//   http.begin(uploadUrl);
//   http.addHeader("Content-Type", "text/plain");
//   http.addHeader("Device-ID", deviceMAC); // Header định danh
  
//   int code = http.POST(encryptedImg);
//   http.end();

//   if (code == 200) {
//     Serial.println("Upload OK. Đợi kết quả...");
//     delay(3000); // Đợi server xử lý AI
    
//     // Lấy kết quả (Polling)
//     HTTPClient httpRes;
//     String resUrl = "http://" + serverIP + ":" + String(serverPort) + "/results?device_id=" + deviceMAC;
//     httpRes.begin(resUrl);
//     if (httpRes.GET() == 200) {
//       String payload = httpRes.getString();
//       JsonDocument doc;
//       deserializeJson(doc, payload);
      
//       bool alert = doc["latest_action"]["is_alert"];
//       if (alert) triggerAlert();
//     }
//     httpRes.end();
//   }
// }
void loop() {
  // 1. Kiểm tra kết nối WiFi
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.disconnect(); WiFi.reconnect(); return;
  }

  // 2. Kiểm tra quyền (Handshake)
  if (!isAuthorized) {
    delay(10000);
    performHandshake();
    return;
  }

  // 3. Kiểm tra thời gian (Interval)
  unsigned long now = millis();
  if (now - lastUploadTime < UPLOAD_INTERVAL) return;
  lastUploadTime = now;

  // --- BẮT ĐẦU CHỤP ẢNH ---
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) return;

  // Mã hóa ảnh
  String encryptedImg = encryptImage(fb->buf, fb->len);
  esp_camera_fb_return(fb); // Giải phóng bộ nhớ camera

  // --- GỬI ẢNH LÊN SERVER ---
  HTTPClient http;
  String uploadUrl = "http://" + serverIP + ":" + String(serverPort) + "/upload";
  http.begin(uploadUrl);
  http.addHeader("Content-Type", "text/plain");
  http.addHeader("Device-ID", deviceMAC); 
  
  int code = http.POST(encryptedImg);
  http.end(); // Đóng kết nối upload

  // --- XỬ LÝ KẾT QUẢ ---
  if (code == 200) {
    Serial.println("Upload OK. Đợi AI xử lý...");
    delay(3000); // Đợi server chạy OpenAI và lưu DB
    
    // Gọi API lấy kết quả
    HTTPClient httpRes;
    String resUrl = "http://" + serverIP + ":" + String(serverPort) + "/results?device_id=" + deviceMAC;
    httpRes.begin(resUrl);
    
    if (httpRes.GET() == 200) {
      String payload = httpRes.getString();
      Serial.println("JSON nhận được: " + payload);

      JsonDocument doc;
      DeserializationError error = deserializeJson(doc, payload);

      if (!error) {
        // Truy cập vào object "latest_action"
        JsonObject latest = doc["latest_action"];
        
        // --- ĐỌC CẤU HÌNH CHI TIẾT TỪ PYTHON GỬI VỀ ---
        // (Lưu ý: Python trả về true/false, ArduinoJson tự chuyển thành bool)
        bool needLight = latest["trigger_light"];
        bool needBuzzer = latest["trigger_buzzer"];

        // --- LOGIC QUYẾT ĐỊNH HÀNH ĐỘNG ---
        if (needLight && needBuzzer) {
          // Trường hợp 1: Bật cả hai
          triggerAlert();
        } 
        else if (needLight) {
          // Trường hợp 2: Chỉ bật đèn
          triggerFlash();
        } 
        else if (needBuzzer) {
          // Trường hợp 3: Chỉ bật còi
          triggerBuzzer();
        }
        else {
          Serial.println("-> Không có cảnh báo hoặc đã tắt trong Setting.");
        }
      } else {
        Serial.print("Lỗi parse JSON: "); Serial.println(error.c_str());
      }
    }
    httpRes.end();
  } else {
    Serial.printf("Lỗi Upload: %d\n", code);
  }
}