# Training data

Everything the Dhuan Detective model was fitted on, where each number came from,
and what it does and does not cover. Every figure here was computed from the
shipped artefacts rather than typed by hand — see
[Reproducing these numbers](#9-reproducing-these-numbers).

**Snapshot digest:** `c7836258415ae075b78a42495f23025871f36047348589588e039da60152ab7a`

---

## 1. What the model actually learns

The model does **not** predict an absolute PM2.5 concentration. It predicts a
**residual** — how much PM2.5 has moved away from what the nearest monitoring
station already reported one hour earlier.

```
target = pm25(station, t) - pm25(station, t - 1h)
```

The number you are shown is then assembled as:

```
final = anchor + predicted_residual + distance_correction
```

Because the station reading is the baseline, "repeat the last reading" is
already a decent prediction, and the model only has to learn the correction on
top of it. The useful consequence: the served interval gets **wider** exactly
when the model expects a real change, instead of shrinking toward a
confident-looking mean.

---

## 2. Sources

| What | Source | Credentials | Terms |
|---|---|---|---|
| Station PM2.5 | OpenAQ public archive bucket | none | OpenAQ public data; attribution CPCB, DPCC, IMD, HSPCB, UPPCB, IITM |
| Weather | Open-Meteo archive API | none | Open-Meteo, free for non-commercial use |

Both are **archival** endpoints, not live feeds. The snapshot therefore ends on
the last hour these archives had published when it was taken, and the served
product labels that staleness explicitly rather than pretending to be current.

A note on station character: several series are **satellite-derived** rather than
ground monitors — station `3024966` is `NASA GSFC Rutgers Calib.`, and several
are `Air Check` units. These are 24-hour averaged estimates reported on an
hourly cadence, not instantaneous ground readings, and they behave differently
in the residuals. They stay in the snapshot because they cover areas no ground
monitor reaches, but it is worth knowing when a single station looks odd.

---

## 3. Snapshot contents

| Field | Value |
|---|---|
| Station observations | **591,372** |
| Weather observations | **211,992** |
| Distinct stations | **73** |
| Distinct sensors | 73 |
| Station time range | 2026-06-14T00:02:42+05:30 → 2026-10-08T23:59:35+05:30 (IST) |
| Weather time range | 2026-06-14T00:00 → 2026-10-12T23:00 |
| Rows with a null value | 0 |
| Compressed size | 5.7 MiB |
| Uncompressed size | 131.3 MiB |

The station series stops on 2026-10-08 while weather runs to 2026-10-12. The
station archive is the scarcer of the two, and training only uses hours where
both a station reading and a weather hour exist.

### Reading distribution (µg/m³)

| Statistic | Value |
|---|---|
| Minimum | 0.0 |
| 25th percentile | 23.0 |
| Median | 36.0 |
| Mean | 42.86 |
| Standard deviation | 33.11 |
| 75th percentile | 54.5 |
| Maximum | 1000.0 |

The mean sits above the median because of long dirty-season tails. The maximum
of exactly `1000.0` is the **CPCB scale ceiling**, not a sensor measurement —
raw values are clipped at 1000 µg/m³ upstream, so rows at the ceiling carry no
information about how dirty it really was. Any estimate built on a saturated
hour is a **lower bound**.

### Weather ranges

| Variable | Min | Max |
|---|---|---|
| Temperature (°C) | 19.7 | 42.3 |
| Relative humidity (%) | 23 | 100 |
| Wind speed | 0.0 | 36.5 |
| Pressure (hPa) | 964.6 | 996.8 |

These span a Delhi summer-to-monsoon transition. Pressure at
964.6 hPa is unusually low and indicates a deep
system; it is a genuine observation, not a data error.

---

## 4. The 27 features

| Feature | Notes |
|---|---|
| `hour` | |
| `hour_sin` | |
| `hour_cos` | |
| `dayofweek` | |
| `month` | |
| `month_sin` | |
| `month_cos` | |
| `wind_speed` | |
| `wind_gust` | |
| `temp_c` | |
| `rh` | |
| `precip` | |
| `wind_dir_sin` | |
| `wind_dir_cos` | |
| `landfill_dist_km` | |
| `landfill_count_5km` | |
| `industrial_dist_km` | |
| `industrial_count_5km` | |
| `construction_dist_km` | |
| `construction_count_5km` | |
| `junction_dist_km` | |
| `junction_count_5km` | |
| `station_lag1` | |
| `station_lag24` | |
| `station_rolling6` | |
| `lat` | |
| `lon` | |

Encoding notes:

- `wind_dir` is stored as an integer 0–359 and split into `wind_dir_sin` /
  `wind_dir_cos`. A raw 359°/0° pair is a discontinuity a tree can only learn
  through many splits; on the unit circle, north is simply far from south.
- `hour` and `month` get the same treatment for the same reason, and are also
  kept raw because trees can use them for ordering effects.
- `station_lag1`, `station_lag24`, `station_rolling6` are the anchor and its
  recent history, from the same station the estimate is anchored to.
- The `*_dist_km` / `*_count_5km` pairs come from the 2,329 classified OSM
  features in `backend/data/delhi_sources.json`.

---

## 5. Stations

All 73 stations, sorted by rows contributed.

| Location id | Rows | Name |
|---|---|---|
| 8239 | 9,651 | Okhla Phase-2, Delhi - DPCC-3379513 |
| 5586 | 9,584 | Sirifort, Delhi - CPCB-3379479 |
| 10486 | 9,514 | Mundka, Delhi - DPCC-3379539 |
| 6936 | 9,442 | Arya Nagar, Bahadurgarh - HSPCB-5911905 |
| 6254665 | 9,441 | Commonwealth Sports Complex, Delhi - DPCC-6224596 |
| 10484 | 9,416 | Sri Aurobindo Marg, Delhi - DPCC-3379540 |
| 5626 | 9,411 | DTU, New Delhi - CPCB-3379478 |
| 6356 | 9,397 | Pusa, Delhi - DPCC-3379541 |
| 6254666 | 9,383 | IGNOU_Maidan Garhi, Delhi - DPCC-6224597 |
| 6938 | 9,380 | Vivek Vihar, Delhi - DPCC-3379520 |
| 6957 | 9,376 | Jawaharlal Nehru Stadium, Delhi - DPCC-3379509 |
| 10485 | 9,373 | Narela, Delhi - DPCC-3379511 |
| 8365 | 9,370 | Nehru Nagar, Delhi - DPCC-3379514 |
| 6986 | 9,312 | Knowledge Park - V, Greater Noida - UPPCB-3379615 |
| 6931 | 9,303 | Dwarka-Sector 8, Delhi - DPCC-3379507 |
| 6254664 | 9,263 | NSUT Jaffarpur, Delhi - DPCC-6224595 |
| 6988 | 9,251 | Sector-116, Noida - UPPCB-3379616 |
| 6254663 | 9,187 | JNU, Delhi - DPCC-6224594 |
| 10919 | 9,083 | Sanjay Nagar, Ghaziabad - UPPCB-3379595 |
| 6929 | 9,037 | Major Dhyan Chand National Stadium, Delhi - DPCC-3379510 |
| 8475 | 9,033 | Sonia Vihar, Delhi - DPCC-3379517 |
| 8917 | 9,015 | Ashok Vihar, Delhi - DPCC-3379505 |
| 5630 | 8,998 | Shadipur, Delhi - CPCB-3379474 |
| 5598 | 8,945 | Sector - 125, Noida, UP - UPPCB-3379526 |
| 6934 | 8,944 | Dr. Karni Singh Shooting Range, Delhi - DPCC-3379506 |
| 5627 | 8,917 | CRRI Mathura Road, New Delhi - IMD-3379466 |
| 6257818 | 8,886 | Cantonment Area, Delhi - DPCC-6227749 |
| 8915 | 8,869 | Wazirpur, Delhi - DPCC-3379519 |
| 50 | 8,784 | Punjabi Bagh, Delhi - DPCC-3379482 |
| 6254594 | 8,781 | Talkatora Garden, Delhi - DPCC-6224525 |
| 10900 | 8,773 | Teri Gram, Gurugram - HSPCB-3379652 |
| 10825 | 8,771 | Sector-51, Gurugram - HSPCB-3379653 |
| 6148686 | 8,757 | IIT Delhi, Delhi - IITM-6118616 |
| 5634 | 8,746 | Lodhi Road, New Delhi - IMD-3379472 |
| 6924 | 8,739 | Indirapuram, Ghaziabad - UPPCB-3379596 |
| 17 | 8,708 | R K Puram, Delhi - DPCC-3379481 |
| 10921 | 8,689 | NISE Gwal Pahari, Gurugram - IMD-3379586 |
| 10488 | 8,685 | Najafgarh, Delhi - DPCC-3379512 |
| 5404 | 8,669 | Pusa, Delhi - IMD-3379470 |
| 5541 | 8,655 | Burari Crossing, New Delhi - IMD-3379467 |
| 5570 | 8,608 | Aya Nagar, New Delhi - IMD-3379471 |
| 10908 | 8,581 | Sector 11, Faridabad - HSPCB-3379651 |
| 5610 | 8,504 | North Campus, DU, Delhi - IMD-3379468 |
| 10920 | 8,496 | New Industrial Town, Faridabad - HSPCB-3379649 |
| 5665 | 8,464 | Vasundhara, Ghaziabad - UPPCB-3379523 |
| 6359 | 8,438 | IHBAS, Dilshad Garden,New Delhi - CPCB-3379475 |
| 6972 | 8,435 | Nathu Colony, Ballabgarh - HSPCB-5980647 |
| 10831 | 8,390 | Rohini, Delhi - DPCC-3379515 |
| 6953 | 8,380 | Sector-2 IMT, Manesar - HSPCB-5933785 |
| 235 | 8,340 | Anand Vihar, New Delhi - DPCC-3379575 |
| 3410004 | 8,318 | Amity University, Panchgaon - IITM-3379939 |
| 5650 | 8,289 | IGI Airport (T3), Delhi - IMD-3379469 |
| 6311324 | 8,232 | Govindpuram, Ghaziabad - UPPCB-6281265 |
| 6358 | 7,991 | Mandir Marg, New Delhi - DPCC-3379480 |
| 6978 | 7,942 | Knowledge Park - III, Greater Noida - UPPCB-3379527 |
| 6932 | 7,721 | Alipur, Delhi - DPCC-3379585 |
| 6299603 | 7,682 | SRM University, Modinagar - UPPCB-6269545 |
| 8235 | 7,637 | Jahangirpuri, Delhi - DPCC-3379508 |
| 6980 | 7,627 | Sector-1, Noida - UPPCB-3379617 |
| 6299678 | 7,474 | Ved Vihar-Loni, Ghaziabad - UPPCB-6269620 |
| 6299494 | 7,434 | 6299494 |
| 7005 | 7,398 | Loni, Ghaziabad - UPPCB-3379597 |
| 301 | 7,324 | Vikas Sadan, Gurugram - HSPCB-5945694 |
| 10820 | 7,251 | Sector 30, Faridabad - HSPCB-3379650 |
| 5622 | 7,128 | NSIT Dwarka, Delhi - CPCB-3379476 |
| 11603 | 6,102 | Chandni Chowk, Delhi - IITM-3379665 |
| 3024966 | 5,310 | NASA GSFC Rutgers Calib. N8-2994922 |
| 6125489 | 2,804 | Uptitude Cloud Pvt Ltd - Sector 62, GGN-6095421 |
| 6145551 | 2,804 | Anand Lok-6115517 |
| 4712609 | 2,802 | Air Check-6188596 |
| 6105800 | 2,798 | Sector 1, Noida extension-6075738 |
| 4663956 | 2,765 | Santushti Apartments, Vasant Kunj-4634402 |
| 8118 | 2,365 | New Delhi-8118 |

---

## 6. Evaluation protocol

Two protocols are run, because they answer different questions.

**Temporal holdout** — train on the earlier part of the series, test on strictly
later hours. Answers: *"given a station I already know, can I predict the next
hour?"*

**Leave-one-station-out** — remove each station in turn, retrain, predict it.
Answers: *"can I place a station I have never seen?"* This is the harder and more
relevant question for a new locality.

### Results

| Protocol | Test rows | MAE | RMSE | R² | 80% coverage |
|---|---|---|---|---|---|
| Future hours | 118,331 | 11.1 | 26.3 | 0.535 | 37.7% |
| Unseen station | 591,372 | 10.6 | 21.6 | 0.566 | 43.0% |

Winner: **`quantile-model`**

### Baselines that were actually measured

| Baseline | MAE (µg/m³) |
|---|---|
| global-mean | 27.15 |
| per-station-climatology | 27.28 |
| persistence-lag1h | 11.64 |

The model beats the naive "repeat the last station reading" baseline by about
4%, and beats seasonal
climatology by more than half. It does **not** blow the naive baseline apart, and
the model card says so rather than implying otherwise.

### Why the coverage column looks alarming

This needs a plain explanation. The **raw** p10/p90 quantile models under-cover
during rapid AQI swings — precisely the hours anyone cares about. So the interval
actually served by the API is not the raw quantile spread; it is a **conformal
interval**, calibrated on held-out data:

> conformal radius (80% target): 15.00 ug/m3; empirical coverage on holdout: 0.804

> Raw quantile p10/p90 models under-cover during rapid AQI swings; the interval served by the API is the conformal one.

The coverage percentages in the table above are the raw quantile models. The
conformal interval is the one you are shown, and it hits its 80% target. Both
numbers are published because quoting only the conformal figure would hide a real
property of the model, and quoting only the raw one would misrepresent the
product.

---

## 7. Known limits

1. **Unseen localities are the weak case.** Even leave-one-station-out MAE is
   ~10.6 µg/m³. For a street several kilometres from any monitor, treat the
   number as a rough guide and check an official station.
2. **Satellite stations are not ground truth.** A handful of the 73 series are
   satellite-derived and behave differently in the residuals.
3. **Saturation.** Raw values clip at 1000 µg/m³ upstream, compressing severe
   episodes at the top of the range.
4. **Transitions dominate the error mass.** Most error sits in the hours when
   wind direction and humidity shift quickly.
5. **No fire-smoke channel.** FIRMS fire data feeds the attribution agent but is
   **not** a training feature, because there is no reliable fire label across all
   73 stations for this period.
6. **Snapshot staleness.** The archive lags real time by days. Live serving uses
   `backend/data/station_index.json`, not this snapshot, and labels staleness
   explicitly.

---

## 8. Files

| Path | Contents |
|---|---|
| `backend/data/training_snapshot.json.gz` | the 591,372-row training snapshot |
| `backend/models/metrics.json` | evaluation results, baselines, feature list |
| `backend/data/delhi_sources.json` | 2,329 classified OSM features |
| `backend/data/station_index.json` | compact live station index |
| `backend/src/dhuan/model/features.py` | feature build and `snapshot_hash` |
| `backend/src/dhuan/model/train.py` | training and evaluation |
| `backend/src/dhuan/model/categories.py` | CPCB category boundaries |

---

## 9. Reproducing these numbers

The digest is computed over the **canonical JSON payload** of the `stations` and
`weather` arrays — *not* over the bytes of the `.gz` file:

```python
blob = json.dumps(
    {"stations": snapshot["stations"], "weather": snapshot["weather"]},
    sort_keys=True,
)
digest = hashlib.sha256(blob.encode()).hexdigest()
```

This matters if you audit provenance: `sha256sum` on the compressed file will
**not** reproduce the digest in `metrics.json`, and that is expected rather than
evidence of tampering.

```bash
make train

python3 - <<'EOF'
import gzip, hashlib, json, pathlib
snap = json.loads(gzip.decompress(
    pathlib.Path("backend/data/training_snapshot.json.gz").read_bytes()))
blob = json.dumps(
    {"stations": snap["stations"], "weather": snap["weather"]}, sort_keys=True)
recorded = json.load(open("backend/models/metrics.json"))["snapshot_sha256"]
actual = hashlib.sha256(blob.encode()).hexdigest()
print("match" if actual == recorded else f"MISMATCH {actual} vs {recorded}")
EOF
```

The same counts are served live at `GET /v1/training-data`, derived from the
shipped artefacts at request time rather than hard-coded.
