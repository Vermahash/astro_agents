import datetime
import sys
sys.path.append('.')
from astro_kp import calculate_vedic_charts

dt = datetime.datetime(1996, 7, 16, 20, 20)
# Make dt timezone aware? Harsh's chart is normally given with tz.
# Let's just pass naive, actually calculate_vedic_charts requires dt_aware.
import pytz
tz = pytz.timezone("Asia/Kolkata")
dt_aware = tz.localize(dt)

res = calculate_vedic_charts("Harsh", dt_aware, 28.6139, 77.2090, gender="Male")
# structured_payload is the 10th item returned.
payload = res[9]
coverage = payload.get("yoga_rule_coverage", {})
print("COVERAGE:")
print(coverage)

matrix = payload.get("yoga_rule_matrix", [])
print("\nYOGAS:")
for row in matrix:
    print(f"- {row['yoga_name']}: {row['final_status']}")
