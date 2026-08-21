import datetime
import pytz
from astro_kp import calculate_unified_kundali

dt_aware = datetime.datetime(1998, 10, 10, 5, 45, tzinfo=pytz.timezone('Asia/Kolkata'))
lat = 30.7288
lon = 76.9472

res = calculate_unified_kundali('Harsh', dt_aware, lat, lon)
payload = res[-3]
timeline = res[-4]

print("1. Auto resolves to:", payload['kp_astrology_matrix']['kp_cusp_engine_used'])
print("3. H3:", payload['cusps']['3']['star_lord'], payload['cusps']['3']['sub_lord'], payload['cusps']['3']['sub_sub_lord'])
print("3. H7:", payload['cusps']['7']['star_lord'], payload['cusps']['7']['sub_lord'], payload['cusps']['7']['sub_sub_lord'])
print("3. H8:", payload['cusps']['8']['star_lord'], payload['cusps']['8']['sub_lord'], payload['cusps']['8']['sub_sub_lord'])

audit = payload['dasha_epoch_audit']
print("4/5. Displayed Moon:", audit['displayed_moon_longitude'], "Dasha Moon:", audit['dasha_moon_longitude'])

print("7. Birth MD:", audit['birth_md_lord'])

for row in timeline:
    if row['md'] == 'Rahu' and row['ad'] == 'Mars' and row['pd'] == 'Moon':
        print(f"9. Rahu/Mars/Moon row: {row['start_solar']} | {row['end_solar']} | Rahu | Mars | Moon")
