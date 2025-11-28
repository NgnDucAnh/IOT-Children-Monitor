package com.example.iot;

import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.bumptech.glide.Glide;
import com.bumptech.glide.load.engine.DiskCacheStrategy;
import com.example.iot.api.RetrofitClient;
import com.example.iot.model.ResultsResponse;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class MainActivity extends AppCompatActivity {

    private TextView txtDateTime, txtStatus;
    private ImageView imgCameraSnapshot;

    private Handler handler;
    private Runnable refreshRunnable;
    private static final int REFRESH_INTERVAL = 15000; // 3 giây tự refresh 1 lần

    private String currentDeviceId;
    private String lastImageUrl = ""; // Biến để tránh load lại ảnh cũ

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        // 1. Lấy Device ID đã lưu từ bước Login/Pairing
        SharedPreferences prefs = getSharedPreferences("IOT_PREFS", MODE_PRIVATE);
        currentDeviceId = prefs.getString("SAVED_DEVICE_ID", null);

        // Nếu chưa có ID (Lỗi logic) -> Quay về Login
        if (currentDeviceId == null) {
            Toast.makeText(this, "Lỗi: Chưa chọn thiết bị!", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }

        // 2. Ánh xạ View
        txtDateTime = findViewById(R.id.dateTimeText);
        txtStatus = findViewById(R.id.statusText);
        imgCameraSnapshot = findViewById(R.id.imgCameraSnapshot);
        Button btnHistory = findViewById(R.id.historyButton);
        Button btnSettings = findViewById(R.id.settingsButton);

        // 3. Setup nút bấm
        btnSettings.setOnClickListener(v -> startActivity(new Intent(MainActivity.this, SettingsActivity.class)));
        btnHistory.setOnClickListener(v -> startActivity(new Intent(MainActivity.this, HistoryActivity.class)));

        // 4. Setup Refresh tự động
        handler = new Handler(Looper.getMainLooper());
        refreshRunnable = new Runnable() {
            @Override
            public void run() {
                fetchDataFromServer();
                handler.postDelayed(this, REFRESH_INTERVAL);
            }
        };
    }

    private void fetchDataFromServer() {
        // Gọi API: GET /results?device_id=...
        RetrofitClient.getService().getResults(currentDeviceId).enqueue(new Callback<ResultsResponse>() {
            @Override
            public void onResponse(Call<ResultsResponse> call, Response<ResultsResponse> response) {
                if (response.isSuccessful() && response.body() != null) {
                    updateUI(response.body());
                } else {
                    Log.e("IOT_APP", "Lỗi Server: " + response.code());
                }
            }

            @Override
            public void onFailure(Call<ResultsResponse> call, Throwable t) {
                Log.e("IOT_APP", "Lỗi Mạng: " + t.getMessage());
            }
        });
    }

    private void updateUI(ResultsResponse data) {
        if (data.latest_action == null) {
            txtStatus.setText("Chưa có dữ liệu mới");
            return;
        }

        ResultsResponse.LatestAction action = data.latest_action;

        // 1. Hiển thị Trạng thái
        txtStatus.setText("Hành động: " + action.action_code);
        if (action.is_alert) {
            txtStatus.setTextColor(Color.RED);
            txtStatus.setText("CẢNH BÁO: " + action.action_code);
        } else {
            txtStatus.setTextColor(Color.BLACK);
        }

        // 2. Hiển thị Thời gian (ĐÃ SỬA)
        String rawTime = action.timestamp;
        // Gọi hàm chuyển đổi để lấy giờ VN
        String timeDisplay = convertUtcToVnTime(rawTime);
        txtDateTime.setText(timeDisplay);

        // 3. Hiển thị Ảnh (Sử dụng Glide)
        String newImageUrl = action.image_url;

        // Chỉ load lại ảnh nếu URL thay đổi (tiết kiệm băng thông)
        if (newImageUrl != null && !newImageUrl.equals(lastImageUrl)) {
            lastImageUrl = newImageUrl;

            Glide.with(this)
                    .load(newImageUrl)
                    .placeholder(R.drawable.ic_launcher_background) // Ảnh chờ (nhớ tạo trong drawable)
                    .error(android.R.drawable.ic_delete)           // Ảnh lỗi
                    .diskCacheStrategy(DiskCacheStrategy.ALL)      // Cache lại cho nhanh
                    .into(imgCameraSnapshot);
        }
    }

    private String convertUtcToVnTime(String utcTimeStr) {
        if (utcTimeStr == null || utcTimeStr.isEmpty()) return "Vừa xong";

        try {
            // 1. Định dạng đầu vào (Khớp với chuỗi server trả về)
            // Ví dụ server trả về: "2025-11-28 13:49:56" (hoặc có thêm múi giờ)
            // Nếu server trả về dạng "Thu, 28 Nov 2025..." như trong ảnh bạn gửi
            // Thì format phải là: "EEE, dd MMM yyyy HH:mm:ss z"
            SimpleDateFormat inputFormat = new SimpleDateFormat("EEE, dd MMM yyyy HH:mm:ss z", Locale.ENGLISH);
            inputFormat.setTimeZone(TimeZone.getTimeZone("GMT")); // Giờ gốc là GMT/UTC

            // 2. Parse chuỗi thành Date
            Date date = inputFormat.parse(utcTimeStr);

            // 3. Định dạng đầu ra (Giờ Việt Nam)
            SimpleDateFormat outputFormat = new SimpleDateFormat("dd/MM/yyyy HH:mm:ss", Locale.getDefault());
            outputFormat.setTimeZone(TimeZone.getTimeZone("Asia/Ho_Chi_Minh")); // Ép sang giờ VN

            return outputFormat.format(date);

        } catch (Exception e) {
            e.printStackTrace();
            return utcTimeStr; // Nếu lỗi format thì trả về nguyên gốc
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        // Bắt đầu refresh khi màn hình hiện lên
        handler.post(refreshRunnable);
    }

    @Override
    protected void onPause() {
        super.onPause();
        // Dừng refresh khi thoát ra hoặc tắt màn hình
        handler.removeCallbacks(refreshRunnable);
    }
}