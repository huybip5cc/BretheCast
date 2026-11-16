# Thời tiết & chất lượng không khí

Ứng dụng Streamlit cho Hà Nội và TP. Hồ Chí Minh, với ba chế độ **Dự báo thời tiết**, **AQI** và **Dự báo & gợi ý hoạt động**.

## Chạy ứng dụng

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

Chạy kiểm thử:

```powershell
python -m pytest -q
```

## Cấu trúc mã nguồn

- `app.py` điều phối vòng đời trang, tải dữ liệu và chọn chế độ hiển thị.
- `ui/` chứa phần trình bày: `styles.py`, `assets.py`, `sidebar.py`, `widgets.py`, `weather.py`, `air_quality.py` và `today.py`.
- `data.py` gọi và chuẩn hóa dữ liệu Open-Meteo; `history_store.py` quản lý lịch sử SQLite.
- `analysis.py`, `health.py` và `activity_rules.py` chứa phân tích AQI, hướng dẫn sức khỏe và quy tắc xếp hạng hoạt động.
- `decision_engine.py` xây dựng đặc trưng, huấn luyện và dự báo.

Ứng dụng cần kết nối Internet tới Open‑Meteo. Nếu API không sẵn sàng, các mục đo hiển thị dấu gạch ngang; ứng dụng không thay bằng số giả.

## Nguồn dữ liệu và cách tính

- Thời tiết: Open‑Meteo Forecast API, đơn vị địa phương, dữ liệu hiện tại, giờ và ngày.
- Chất lượng không khí: Open‑Meteo Air Quality API (CAMS), US AQI hoặc European AQI, PM₂.₅ và các chỉ số khí ô nhiễm.
- Chuỗi AQI quá khứ từ API là **ước tính/dự báo mô hình lưu trữ**, không phải quan trắc tại trạm. Ứng dụng lưu lần đầu giá trị API theo thành phố và mốc giờ trong `.aqi_data/history.sqlite3`; chỉ lưu các mốc quá khứ, không lưu dự báo tương lai.
- Giá trị AQI từng ngày trong dải dự báo là trung bình số học của các giờ dự báo có dữ liệu trong ngày. Ngày và giờ không có mẫu sẽ để trống.
- “Khung 3 giờ AQI thường cao” tính AQI trung bình lịch sử theo từng giờ trong ngày rồi tìm cửa sổ 3 giờ liên tiếp có trung bình cao nhất; chỉ có kết quả khi có ít nhất 24 mẫu AQI hợp lệ và dữ liệu ở ít nhất 3 giờ trong ngày. Heatmap nhóm trung bình theo thứ trong tuần và giờ, bỏ qua ô thiếu.
- Khuyến nghị sức khỏe với US AQI theo các dải hướng dẫn chung của EPA; lựa chọn nhóm chỉ điều chỉnh cách diễn đạt, không tự đặt ngưỡng khác nhau. Với EU AQI, khuyến nghị là nhắc nhở thận trọng theo chính dải EU AQI, không suy luận ngưỡng EPA hay rủi ro y tế riêng cho nhóm.

## Dự báo & gợi ý hoạt động

- `decision_engine.py` ghép AQI và thời tiết theo giờ, tạo đặc trưng từ dữ liệu đã có, chia tập theo thời gian và chừa khoảng bằng chân trời dự báo.
- Cảnh báo 6/12/24 giờ dùng Logistic Regression có chuẩn hóa đặc trưng; được so sánh trên đoạn thời gian mới nhất với tỉ lệ nền và quy tắc “AQI hiện tại đã vượt ngưỡng”. Mốc báo 25% thể hiện giả định vận hành bỏ sót đợt xấu tốn kém gấp 3 lần cảnh báo nhầm; đây không phải ngưỡng y tế.
- Mô hình được cache trong tiến trình theo thành phố và dữ liệu đầu vào. Mỗi lần dữ liệu Open‑Meteo đổi, cache tự tạo bản đánh giá mới.
- Ứng dụng không dùng mô hình để dự đoán trị số AQI. Trong phần gợi ý hoạt động, AQI theo giờ lấy từ Open‑Meteo; giờ thiếu để trống, không nội suy hoặc thay bằng dự đoán ML.
- `activity_rules.py` xếp hạng các cửa sổ liên tiếp theo giờ xấu nhất trước rồi theo trung bình; chỉ dùng giờ có AQI, không nội suy. Dải AQI theo AirNow/EPA, UV theo WHO và chỉ số nhiệt theo NOAA/NWS; trọng số hoạt động chỉ để xếp hạng tiện ích, không thay đổi ngưỡng sức khỏe theo nhóm.
- Kiểm thử logic tách chuỗi, chấm điểm giờ và xếp hạng khung giờ nằm trong `tests/`.

## Giới hạn

AQI và PM₂.₅ là sản phẩm mô hình CAMS ở độ phân giải lưới, không tương đương cảm biến tại địa chỉ cụ thể. API được hỏi tối đa 90 ngày quá khứ; SQLite lưu lịch sử trong cùng khoảng thời gian. Mô hình cảnh báo vượt ngưỡng là thử nghiệm trên chuỗi CAMS, chưa được xác nhận bằng thiết bị đo độc lập. Nếu lịch sử, lớp sự kiện hoặc các mốc liên tục không đủ, ứng dụng không hiển thị kết quả như đã kiểm chứng.

Nguồn dữ liệu và ghi nhận: [Open‑Meteo](https://open-meteo.com/) và [CAMS](https://atmosphere.copernicus.eu/). Hướng dẫn sức khỏe: [US EPA AQI](https://www.airnow.gov/aqi/aqi-basics/).
