"""สร้าง sentinel2.html — Sentinel-2 median composite ปลอดเมฆ เฉพาะประเทศไทย
ซ้อนบนพื้นหลัง Google Maps Satellite

การใช้งาน:
    env\\Scripts\\earthengine.exe authenticate     # ทำครั้งเดียว
    env\\Scripts\\python.exe sentinel2_gee.py --project ee-xxxxx

หรือกำหนด project ผ่าน environment variable EE_PROJECT แล้วรันเปล่า ๆ

หมายเหตุ: tile URL ที่ได้จาก getMapId เป็น token ชั่วคราว (หมดอายุราว 3 วัน)
เมื่อภาพในหน้าเว็บหายให้รันสคริปต์นี้ใหม่
"""

import argparse
import datetime as dt
import json
import os
import sys

import ee

# ---------------------------------------------------------------- ค่าตั้งต้น
START_DATE = "2026-01-01"
END_DATE = dt.date.today().isoformat()  # ปี 2026 ยังไม่จบ ใช้ข้อมูลถึงวันที่รัน

# Cloud Score+ : ยิ่งใกล้ 1 ยิ่งใส. 0.60 = สมดุลระหว่างกำจัดเมฆบางกับไม่ทิ้ง pixel ดี
CS_THRESHOLD = 0.60

VIS = {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000}

OUT_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sentinel2.html")


def build_composite():
    thailand = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017").filter(
        ee.Filter.eq("country_na", "Thailand")
    )

    # QA60 หยุดเติมข้อมูลตั้งแต่ ก.พ. 2022 จึง mask เมฆด้วย Cloud Score+ แทน
    csplus = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")

    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(thailand)
        .filterDate(START_DATE, END_DATE)
        .linkCollection(csplus, ["cs"])
        .map(lambda img: img.updateMask(img.select("cs").gte(CS_THRESHOLD)))
    )

    composite = s2.median().clip(thailand)
    return composite, s2


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sentinel-2 ประเทศไทย {start} – {end} (Median ปลอดเมฆ)</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body {{ margin: 0; height: 100%; }}
  #map {{ height: 100%; }}
  .info-box {{
    padding: 8px 12px; background: rgba(255,255,255,.9);
    border-radius: 6px; box-shadow: 0 1px 5px rgba(0,0,0,.3);
    font: 14px/1.4 sans-serif;
  }}
  .info-box input[type=range] {{ width: 160px; vertical-align: middle; }}
</style>
</head>
<body>
<div id="map"></div>
<script>
var map = L.map('map');

// Google Maps tile layers
var gSat = L.tileLayer('https://mt1.google.com/vt/lyrs=s&x={{x}}&y={{y}}&z={{z}}', {{
  maxZoom: 20, attribution: '&copy; Google Maps'
}});
var gHybrid = L.tileLayer('https://mt1.google.com/vt/lyrs=y&x={{x}}&y={{y}}&z={{z}}', {{
  maxZoom: 20, attribution: '&copy; Google Maps'
}});
var gRoad = L.tileLayer('https://mt1.google.com/vt/lyrs=m&x={{x}}&y={{y}}&z={{z}}', {{
  maxZoom: 20, attribution: '&copy; Google Maps'
}});
gSat.addTo(map);

// Sentinel-2 median composite จาก Google Earth Engine
var s2 = L.tileLayer('{tile_url}', {{
  maxZoom: 20, opacity: 1.0,
  attribution: 'Sentinel-2 / Copernicus &mdash; Google Earth Engine'
}}).addTo(map);

map.fitBounds([[5.61, 97.34], [20.47, 105.64]]);   // ขอบเขตประเทศไทย

L.control.layers(
  {{ 'Google ดาวเทียม': gSat, 'Google ผสม (Hybrid)': gHybrid, 'Google แผนที่ถนน': gRoad }},
  {{ 'Sentinel-2 สีผสมจริง': s2 }}
).addTo(map);

L.control.scale({{ metric: true, imperial: false }}).addTo(map);

// แถบปรับความโปร่งใสของภาพ Sentinel-2 เพื่อเทียบกับพื้นหลัง Google
var opacityBox = L.control({{ position: 'topright' }});
opacityBox.onAdd = function () {{
  var div = L.DomUtil.create('div', 'info-box');
  div.innerHTML =
    'ความทึบ Sentinel-2: <span id="opv">100%</span><br>' +
    '<input id="op" type="range" min="0" max="100" value="100">';
  L.DomEvent.disableClickPropagation(div);
  return div;
}};
opacityBox.addTo(map);
document.getElementById('op').addEventListener('input', function (e) {{
  var v = e.target.value;
  s2.setOpacity(v / 100);
  document.getElementById('opv').textContent = v + '%';
}});

// กล่องแสดงพิกัดตามเมาส์
var coordBox = L.control({{ position: 'bottomleft' }});
coordBox.onAdd = function () {{
  this._div = L.DomUtil.create('div', 'info-box');
  this._div.innerHTML = 'เลื่อนเมาส์เพื่อดูพิกัด';
  return this._div;
}};
coordBox.addTo(map);
map.on('mousemove', function (e) {{
  coordBox._div.innerHTML = 'Lat: ' + e.latlng.lat.toFixed(5) + ' , Lon: ' + e.latlng.lng.toFixed(5);
}});

// กล่องข้อมูลภาพ
var infoBox = L.control({{ position: 'bottomright' }});
infoBox.onAdd = function () {{
  var div = L.DomUtil.create('div', 'info-box');
  div.innerHTML =
    '<b>Sentinel-2 SR Harmonized</b><br>' +
    'ช่วงเวลา: {start} ถึง {end}<br>' +
    'Median ปลอดเมฆ (Cloud Score+ &ge; {cs})<br>' +
    'จำนวนภาพ: {n_images} scene<br>' +
    '<small>สร้างเมื่อ {generated} &middot; tile หมดอายุใน ~3 วัน</small>';
  return div;
}};
infoBox.addTo(map);
</script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        default=os.environ.get("EE_PROJECT"),
        help="Google Cloud project ID ที่เปิด Earth Engine API ไว้",
    )
    args = parser.parse_args()

    if not args.project:
        sys.exit(
            "ต้องระบุ Earth Engine project ID\n"
            "  env\\Scripts\\python.exe sentinel2_gee.py --project ee-xxxxx\n"
            "หรือตั้ง environment variable EE_PROJECT"
        )

    try:
        ee.Initialize(project=args.project)
    except Exception as e:
        sys.exit(
            f"เชื่อมต่อ Earth Engine ไม่สำเร็จ: {e}\n"
            "ถ้ายังไม่เคย auth ให้รัน: env\\Scripts\\earthengine.exe authenticate"
        )

    print(f"ช่วงเวลา {START_DATE} ถึง {END_DATE}")
    composite, masked = build_composite()

    n_images = masked.size().getInfo()
    print(f"จำนวนภาพที่เข้าเงื่อนไข: {n_images:,} scene")
    if n_images == 0:
        sys.exit("ไม่พบภาพในช่วงเวลาที่กำหนด")

    print("กำลังขอ tile URL จาก Earth Engine ...")
    tile_url = composite.getMapId(VIS)["tile_fetcher"].url_format

    html = HTML_TEMPLATE.format(
        tile_url=tile_url,
        start=START_DATE,
        end=END_DATE,
        cs=CS_THRESHOLD,
        n_images=f"{n_images:,}",
        generated=dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"เขียนไฟล์แล้ว: {OUT_HTML}")


if __name__ == "__main__":
    main()
