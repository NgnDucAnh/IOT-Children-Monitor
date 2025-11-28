package com.example.iot.api;

import com.example.iot.model.ConfigBody;
import com.example.iot.model.ConfigResponse;
import com.example.iot.model.DeviceResponse;
import com.example.iot.model.ResultsResponse;
import com.example.iot.model.UserBody;
import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.POST;
import retrofit2.http.GET;
import retrofit2.http.Query;

public interface ApiService {
    // 1. Kiểm tra thiết bị của user
    @POST("/api/get-my-devices")
    Call<DeviceResponse> getMyDevices(@Body UserBody body);

    // 2. Bắt đầu ghép đôi
    @POST("/api/start-pairing")
    Call<Object> startPairing(@Body UserBody body); // Object vì ta chỉ cần check status 200

    @GET("/results")
    Call<ResultsResponse> getResults(@Query("device_id") String deviceId);

    @GET("/get-settings")
    Call<ConfigResponse> getSettings(@Query("device_id") String deviceId);

    // 2. Cập nhật cấu hình
    @POST("/update-settings")
    Call<Object> updateSettings(@Body ConfigBody body);
}