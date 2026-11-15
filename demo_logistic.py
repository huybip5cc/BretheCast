"""Demo thuyết trình: in từng bước Logistic Regression tính xác suất AQI vượt ngưỡng.

python demo_logistic.py            # Hà Nội, ngưỡng mặc định, 6 giờ
python demo_logistic.py "TP. Hồ Chí Minh" 12
"""
import sys

import decision_engine as de
from data import get_air_quality, get_weather

city = sys.argv[1] if len(sys.argv) > 1 else "Hà Nội"
horizon = int(sys.argv[2]) if len(sys.argv) > 2 else 6
threshold = de.thresholds_for_city(city)[0]

weather, air = get_weather(city), get_air_quality(city)
data = de.supervised_table(weather["hourly"], air["hourly"], horizon, peak=True)
result = de._fit_classifier(data, horizon, threshold)
latest = de.build_feature_frame(weather["hourly"], air["hourly"]).query("not is_forecast").dropna(subset=list(de.FEATURES)).iloc[-1]

print(f"\n{city}: khả năng AQI vượt {threshold} trong {horizon} giờ tới | dữ liệu học: {result['train_n']} giờ, thi: {result['test_n']} giờ")
if result["status"] != "ready":
    sys.exit(f"Chưa đủ dữ liệu: {result.get('reason')}")
e = de.explain_probability(result, latest)
print(f"\n{'yếu tố':<28}{'giá trị':>10}{'chuẩn hóa z':>13}{'trọng số w':>12}{'w × z':>9}")
for r in sorted(e["rows"], key=lambda r: -abs(r["contribution"])):
    label = de.FEATURE_LABELS[r['feature']] + (" (sin)" if r['feature'].endswith("sin") else " (cos)" if r['feature'].endswith("cos") else "")
    print(f"{label:<28}{r['value']:>10.1f}{r['z']:>13.2f}{r['weight']:>12.2f}{r['contribution']:>+9.2f}")
print(f"{'hệ số chặn b':<28}{'':>10}{'':>13}{'':>12}{e['intercept']:>+9.2f}")
print(f"\nlogit = b + Σ(w × z) = {e['logit']:+.2f}   ->   xác suất = 1 / (1 + e^(-logit)) = {e['probability']:.1%}")
m, c, p = result["metrics"], result["climatology"], result["current_over_threshold"]
print(f"\nKiểm tra trên {m['n']} giờ chưa từng thấy (Brier càng thấp càng tốt):")
print(f"  mô hình {m['brier']:.3f} | luôn đoán tần suất chung {c['brier']:.3f} | 'đang vượt thì sẽ vượt' {p['brier']:.3f}")
