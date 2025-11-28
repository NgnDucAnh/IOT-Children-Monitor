package com.example.iot.model;
import java.util.List;

public class ResultsResponse {
    public LatestAction latest_action;
    // public Config current_config;
    public List<LatestAction> history;

    public static class LatestAction {
        public String action_code;
        public boolean is_alert;
        public String image_filename;
        public String timestamp;

        // --- Đã thêm trường này để khớp với Server ---
        public String image_url;
        public String message;
    }
}