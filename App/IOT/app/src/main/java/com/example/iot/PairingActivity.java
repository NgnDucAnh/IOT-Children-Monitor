package com.example.iot;

import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.os.Handler;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;
import com.example.iot.api.RetrofitClient;
import com.example.iot.model.DeviceResponse;
import com.example.iot.model.UserBody;
import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class PairingActivity extends AppCompatActivity {

    private String userId;
    private Handler handler = new Handler();
    private Runnable checkDeviceRunnable;
    private boolean isPaired = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_pairing);

        // Lấy User ID được truyền từ màn hình Đăng nhập sang
        userId = getIntent().getStringExtra("USER_ID");

        // 1. Báo Server: Tôi đang chờ
        startPairingMode();

        // 2. Bắt đầu vòng lặp kiểm tra (Polling) mỗi 3 giây
        startPolling();
    }

    private void startPairingMode() {
        RetrofitClient.getService().startPairing(new UserBody(userId)).enqueue(new Callback<Object>() {
            @Override
            public void onResponse(Call<Object> call, Response<Object> response) {
                // Đã báo server xong, chỉ cần đợi.
            }
            @Override
            public void onFailure(Call<Object> call, Throwable t) {
                Toast.makeText(PairingActivity.this, "Lỗi mạng!", Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void startPolling() {
        checkDeviceRunnable = new Runnable() {
            @Override
            public void run() {
                if (isPaired) return; // Nếu xong rồi thì thôi

                checkIfDeviceConnected();

                // Lặp lại sau 3 giây
                handler.postDelayed(this, 3000);
            }
        };
        handler.post(checkDeviceRunnable);
    }

    private void checkIfDeviceConnected() {
        // Hỏi Server: "User này có thiết bị nào chưa?"
        RetrofitClient.getService().getMyDevices(new UserBody(userId)).enqueue(new Callback<DeviceResponse>() {
            @Override
            public void onResponse(Call<DeviceResponse> call, Response<DeviceResponse> response) {
                if (response.isSuccessful() && response.body() != null) {
                    if (response.body().count > 0) {
                        // === TÌM THẤY THIẾT BỊ! ===
                        isPaired = true;
                        String deviceId = response.body().devices.get(0).device_id;

                        // Lưu lại
                        SharedPreferences prefs = getSharedPreferences("IOT_PREFS", MODE_PRIVATE);
                        prefs.edit().putString("SAVED_DEVICE_ID", deviceId).apply();

                        Toast.makeText(PairingActivity.this, "Ghép đôi thành công!", Toast.LENGTH_LONG).show();

                        // Vào Main
                        Intent intent = new Intent(PairingActivity.this, MainActivity.class);
                        intent.putExtra("USER_ID", userId);
                        startActivity(intent);
                        finish();
                    }
                }
            }

            @Override
            public void onFailure(Call<DeviceResponse> call, Throwable t) {
                // Lỗi mạng thì cứ lẳng lặng thử lại sau
            }
        });
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        // Dừng vòng lặp khi thoát màn hình để tránh tốn pin
        handler.removeCallbacks(checkDeviceRunnable);
    }
}