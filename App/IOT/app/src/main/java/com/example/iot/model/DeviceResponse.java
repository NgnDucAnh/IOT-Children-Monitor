package com.example.iot.model;
import java.util.List;

public class DeviceResponse {
    public String status;
    public int count;
    public List<DeviceInfo> devices;

    public static class DeviceInfo {
        public String device_id;
        // Các trường khác (config, created_at) có thể thêm sau nếu cần
    }
}