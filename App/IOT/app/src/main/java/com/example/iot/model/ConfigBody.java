package com.example.iot.model;

public class ConfigBody {
    public String device_id; // Thêm cái này
    public String action;    // "sleeping"
    public String target;    // "enable_light"
    public boolean enabled;
    public Object value;


    public ConfigBody(String device_id, String action, String target, boolean enabled) {
        this.device_id = device_id;
        this.action = action;
        this.target = target;
        this.enabled = enabled;
        this.value = enabled;
    }
}