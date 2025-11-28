package com.example.iot.model;

public class ConfigResponse {
    public String status;
    public ConfigMap config; // Đổi tên class con cho đỡ nhầm


    public static class ConfigMap {
        public ActionDetail sleeping;
        public ActionDetail using_phone;
        public ActionDetail using_computer;
        public ActionDetail no_person;
        public GeneralDetail general;
        public Schedule schedule;
    }

    public static class ActionDetail {
        public boolean enable_light;
        public boolean enable_buzzer;
    }

    public static class GeneralDetail {
        public boolean master_light;
        public boolean master_buzzer;
    }

    public static class Schedule {
        public String start_time;
        public String end_time;
        public boolean enabled;
    }
}