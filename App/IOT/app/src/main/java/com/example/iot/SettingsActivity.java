package com.example.iot;

import android.app.TimePickerDialog;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.util.Log;
import android.widget.CompoundButton;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.TimePicker;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.example.iot.api.RetrofitClient;
import com.example.iot.model.ConfigBody;
import com.example.iot.model.ConfigResponse;

import java.util.Locale;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class SettingsActivity extends AppCompatActivity {

    // --- KHAI BÁO SWITCH ---
    private Switch swMasterLight, swMasterBuzzer;
    private Switch swLightSleep, swLightPhone, swLightLaptop, swLightNoPerson;
    private Switch swAlarmSleep, swAlarmPhone, swAlarmLaptop, swAlarmNoPerson;

    // --- KHAI BÁO TEXTVIEW GIỜ ---
    private TextView tvStartTime, tvEndTime;

    private String currentDeviceId;
    private boolean isUpdatingUI = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_settings);

        // 1. Lấy Device ID
        SharedPreferences prefs = getSharedPreferences("IOT_PREFS", MODE_PRIVATE);
        currentDeviceId = prefs.getString("SAVED_DEVICE_ID", null);

        if (currentDeviceId == null) {
            Toast.makeText(this, "Lỗi: Không tìm thấy thiết bị!", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }

        // 2. Ánh xạ & Sự kiện
        mapViews();
        setupEventListeners();

        // 3. Tải dữ liệu ban đầu
        loadSettingsFromAPI();
    }

    private void mapViews() {
        // TextView Giờ
        tvStartTime = findViewById(R.id.tvStartTime);
        tvEndTime = findViewById(R.id.tvEndTime);

        // Nút Tổng
        swMasterLight = findViewById(R.id.light);
        swMasterBuzzer = findViewById(R.id.alarm);

        // Nhóm Đèn
        swLightSleep = findViewById(R.id.lightSleep);
        swLightPhone = findViewById(R.id.lightPhone);
        swLightLaptop = findViewById(R.id.lightLaptop);
        swLightNoPerson = findViewById(R.id.lightNoPerson);

        // Nhóm Còi
        swAlarmSleep = findViewById(R.id.alarmSleep);
        swAlarmPhone = findViewById(R.id.alarmPhone);
        swAlarmLaptop = findViewById(R.id.alarmLaptop);
        swAlarmNoPerson = findViewById(R.id.alarmNoPerson);
    }

    // --- PHẦN 1: TẢI CẤU HÌNH TỪ SERVER ---
    private void loadSettingsFromAPI() {
        RetrofitClient.getService().getSettings(currentDeviceId).enqueue(new Callback<ConfigResponse>() {
            @Override
            public void onResponse(Call<ConfigResponse> call, Response<ConfigResponse> response) {
                if (response.isSuccessful() && response.body() != null) {
                    if (response.body().config != null) {
                        applySettingsToUI(response.body().config);
                    }
                }
            }
            @Override
            public void onFailure(Call<ConfigResponse> call, Throwable t) {
                Toast.makeText(SettingsActivity.this, "Lỗi kết nối", Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void applySettingsToUI(ConfigResponse.ConfigMap config) {
        isUpdatingUI = true; // Chặn gửi ngược lại server khi đang set UI

        // 1. Cập nhật Giờ giấc (Schedule)
        if (config.schedule != null) {
            tvStartTime.setText(config.schedule.start_time);
            tvEndTime.setText(config.schedule.end_time);
        }

        // 2. Cập nhật Nút Tổng
        if (config.general != null) {
            swMasterLight.setChecked(config.general.master_light);
            swMasterBuzzer.setChecked(config.general.master_buzzer);

            // Cập nhật trạng thái mờ/tỏ
            updateSubSwitchesState(true, config.general.master_light);
            updateSubSwitchesState(false, config.general.master_buzzer);
        }

        // 3. Cập nhật Nhóm Đèn con
        if (config.sleeping != null) swLightSleep.setChecked(config.sleeping.enable_light);
        if (config.using_phone != null) swLightPhone.setChecked(config.using_phone.enable_light);
        if (config.using_computer != null) swLightLaptop.setChecked(config.using_computer.enable_light);
        if (config.no_person != null) swLightNoPerson.setChecked(config.no_person.enable_light);

        // 4. Cập nhật Nhóm Còi con
        if (config.sleeping != null) swAlarmSleep.setChecked(config.sleeping.enable_buzzer);
        if (config.using_phone != null) swAlarmPhone.setChecked(config.using_phone.enable_buzzer);
        if (config.using_computer != null) swAlarmLaptop.setChecked(config.using_computer.enable_buzzer);
        if (config.no_person != null) swAlarmNoPerson.setChecked(config.no_person.enable_buzzer);

        isUpdatingUI = false; // Mở khóa
    }

    private void updateSubSwitchesState(boolean isLightGroup, boolean isEnabled) {
        if (isLightGroup) {
            swLightSleep.setEnabled(isEnabled);
            swLightPhone.setEnabled(isEnabled);
            swLightLaptop.setEnabled(isEnabled);
            swLightNoPerson.setEnabled(isEnabled);
        } else {
            swAlarmSleep.setEnabled(isEnabled);
            swAlarmPhone.setEnabled(isEnabled);
            swAlarmLaptop.setEnabled(isEnabled);
            swAlarmNoPerson.setEnabled(isEnabled);
        }
    }

    // --- PHẦN 2: XỬ LÝ SỰ KIỆN ---
    private void setupEventListeners() {
        // --- GIỜ GIẤC ---
        tvStartTime.setOnClickListener(v -> showCustomTimePicker(tvStartTime, "start_time"));
        tvEndTime.setOnClickListener(v -> showCustomTimePicker(tvEndTime, "end_time"));

        // --- NÚT TỔNG ---
        swMasterLight.setOnCheckedChangeListener((buttonView, isChecked) -> {
            updateSubSwitchesState(true, isChecked);
            if (!isUpdatingUI) sendConfigToServer("general", "master_light", isChecked);
        });

        swMasterBuzzer.setOnCheckedChangeListener((buttonView, isChecked) -> {
            updateSubSwitchesState(false, isChecked);
            if (!isUpdatingUI) sendConfigToServer("general", "master_buzzer", isChecked);
        });

        // --- NÚT CON ---
        setupSwitch(swLightSleep, "sleeping", "enable_light");
        setupSwitch(swLightPhone, "using_phone", "enable_light");
        setupSwitch(swLightLaptop, "using_computer", "enable_light");
        setupSwitch(swLightNoPerson, "no_person", "enable_light");

        setupSwitch(swAlarmSleep, "sleeping", "enable_buzzer");
        setupSwitch(swAlarmPhone, "using_phone", "enable_buzzer");
        setupSwitch(swAlarmLaptop, "using_computer", "enable_buzzer");
        setupSwitch(swAlarmNoPerson, "no_person", "enable_buzzer");
    }

    private void showCustomTimePicker(TextView targetView, String targetKey) {
        // Tách giờ hiện tại để hiển thị mặc định
        int hour = 8;
        int minute = 0;
        try {
            String[] parts = targetView.getText().toString().split(":");
            if (parts.length == 2) {
                hour = Integer.parseInt(parts[0]);
                minute = Integer.parseInt(parts[1]);
            }
        } catch (Exception ignored) {}

        // Hiển thị TimePicker
        new TimePickerDialog(this,
                (TimePicker view, int hourOfDay, int minuteOfHour) -> {
                    // Format giờ thành "08:05"
                    String timeFormatted = String.format(Locale.getDefault(), "%02d:%02d", hourOfDay, minuteOfHour);

                    // Hiển thị lên UI
                    targetView.setText(timeFormatted);

                    // Gửi lên Server
                    sendConfigTimeToServer("schedule", targetKey, timeFormatted);
                },
                hour,
                minute,
                true // 24h format
        ).show();
    }

    private void setupSwitch(Switch sw, String actionKey, String targetKey) {
        sw.setOnCheckedChangeListener((CompoundButton buttonView, boolean isChecked) -> {
            if (isUpdatingUI) return;
            sendConfigToServer(actionKey, targetKey, isChecked);
        });
    }

    // --- PHẦN 3: GỬI API ---

    // Gửi ON/OFF (Boolean)
    private void sendConfigToServer(String action, String target, boolean enabled) {
        ConfigBody body = new ConfigBody(currentDeviceId, action, target, enabled);
        callUpdateAPI(body);
    }

    // Gửi GIỜ (String) - Cần đảm bảo ConfigBody hỗ trợ String value
    private void sendConfigTimeToServer(String action, String target, String timeValue) {
        // Lưu ý: ConfigBody cần constructor hỗ trợ String value
        // Hoặc bạn có thể dùng constructor cũ nhưng set field value riêng
        ConfigBody body = new ConfigBody(currentDeviceId, action, target, true); // true là placeholder
        body.value = timeValue; // Gán đè giá trị string
        callUpdateAPI(body);
    }

    private void callUpdateAPI(ConfigBody body) {
        RetrofitClient.getService().updateSettings(body).enqueue(new Callback<Object>() {
            @Override
            public void onResponse(Call<Object> call, Response<Object> response) {
                if (!response.isSuccessful()) {
                    Toast.makeText(SettingsActivity.this, "Lỗi server: " + response.code(), Toast.LENGTH_SHORT).show();
                }
            }
            @Override
            public void onFailure(Call<Object> call, Throwable t) {
                Toast.makeText(SettingsActivity.this, "Lỗi mạng!", Toast.LENGTH_SHORT).show();
            }
        });
    }
}