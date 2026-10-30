"""Compact AQI advice using EPA's standard AQI bands and activity guidance."""

from analysis import PM25_CONCENTRATION_BANDS

TARGET_GROUPS = (
    "Người đi làm / sinh hoạt thông thường",
    "Người tập thể dục ngoài trời",
    "Trẻ nhỏ",
    "Người cao tuổi",
    "Người có bệnh hô hấp / tim mạch",
)


def impact_summary(aqi: float | None, standard: str = "US AQI") -> str:
    """Describe the likely population-level meaning of an AQI band in plain language."""
    if aqi is None or aqi != aqi:  # None or NaN
        return "—"
    if standard == "EU AQI":
        if aqi <= 20:
            return "Không khí tốt; sinh hoạt ngoài trời bình thường."
        if aqi <= 40:
            return "Hầu hết mọi người có thể sinh hoạt như thường lệ."
        if aqi <= 60:
            return "Người nhạy cảm có thể thấy khó chịu khi gắng sức ngoài trời."
        if aqi <= 80:
            return "Có thể gây kích ứng mắt, ho hoặc đau họng khi vận động mạnh."
        if aqi <= 100:
            return "Ảnh hưởng sức khỏe rõ hơn; người nhạy cảm nên giảm hoạt động ngoài trời."
        return "Không khí rất kém; tránh hoạt động thể chất ngoài trời."
    if aqi <= 50:
        return "Ít hoặc không có nguy cơ ảnh hưởng sức khỏe."
    if aqi <= 100:
        return "Người nhạy cảm có thể bị ảnh hưởng."
    if aqi <= 150:
        return "Nhóm nhạy cảm có thể gặp ảnh hưởng sức khỏe."
    if aqi <= 200:
        return "Một số người có thể bị ảnh hưởng; nhóm nhạy cảm dễ bị tác động hơn."
    if aqi <= 300:
        return "Nguy cơ ảnh hưởng sức khỏe tăng với tất cả mọi người."
    return "Mức cảnh báo khẩn cấp; mọi người đều có nguy cơ bị ảnh hưởng."


def recommendation(aqi: float | None, group: str, standard: str = "US AQI") -> str:
    if aqi is None:
        return "—"
    if standard == "EU AQI":
        if aqi <= 20:
            return "Mức tốt; có thể sinh hoạt ngoài trời bình thường."
        if aqi <= 40:
            return "Mức khá; duy trì sinh hoạt và theo dõi triệu chứng nếu nhạy cảm."
        if aqi <= 60:
            return "Mức trung bình; nhóm nhạy cảm cân nhắc giảm gắng sức kéo dài ngoài trời."
        if aqi <= 80:
            return "Mức kém; giảm vận động gắng sức kéo dài ngoài trời."
        if aqi <= 100:
            return "Mức rất kém; hạn chế hoạt động ngoài trời, theo dõi cảnh báo địa phương."
        return "Mức cực kém; hạn chế ra ngoài và theo dõi hướng dẫn y tế địa phương."
    sensitive = group != TARGET_GROUPS[0]
    if aqi <= 50:
        return "Chất lượng không khí tốt; có thể sinh hoạt ngoài trời bình thường."
    if aqi <= 100:
        return "Không khí ở mức chấp nhận được; cân nhắc giảm vận động mạnh nếu nhạy cảm."
    if aqi <= 150:
        if sensitive:
            return "Giảm vận động kéo dài hoặc cường độ cao ngoài trời; theo dõi triệu chứng."
        return "Có thể duy trì sinh hoạt; cân nhắc nghỉ ngơi nếu thấy khó chịu."
    if aqi <= 200:
        if sensitive:
            return "Tránh vận động mạnh ngoài trời; chọn hoạt động trong nhà nếu có thể."
        return "Giảm hoạt động ngoài trời kéo dài hoặc gắng sức."
    if aqi <= 300:
        return "Hạn chế hoạt động ngoài trời; nhóm nhạy cảm nên ở trong nhà."
    return "Hạn chế ra ngoài và giảm tiếp xúc với không khí ô nhiễm."


def pm25_recommendation(concentration: float | None, group: str, standard: str = "US AQI") -> str:
    """Give concise activity guidance from PM₂.₅ concentration bands."""
    if concentration is None:
        return "—"
    if concentration != concentration:  # NaN
        return "—"

    level = next(
        (index for index, (ceiling, _label, _color) in enumerate(PM25_CONCENTRATION_BANDS[standard]) if concentration <= ceiling),
        len(PM25_CONCENTRATION_BANDS[standard]) - 1,
    )
    sensitive = group != TARGET_GROUPS[0]
    if level == 0:
        return "Có thể sinh hoạt ngoài trời bình thường."
    if level == 1:
        return "Nhóm nhạy cảm nên giảm vận động gắng sức kéo dài ngoài trời." if sensitive else "Có thể sinh hoạt bình thường; hạn chế vận động gắng sức nếu thấy khó chịu."
    if level == 2:
        return "Giảm vận động gắng sức ngoài trời, nhất là với nhóm nhạy cảm."
    if level == 3:
        return "Hạn chế thời gian ngoài trời; ưu tiên không gian trong nhà sạch."
    if level == 4:
        return "Ở trong nhà khi có thể; tránh vận động ngoài trời."
    return "Tránh hoạt động ngoài trời; ở trong nhà và theo dõi cảnh báo địa phương."
