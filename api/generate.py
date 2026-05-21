"""
TRMNL Tokyo Dashboard — data generator
Runs via GitHub Actions on a schedule, writes api/data.json
which TRMNL polls as the plugin's Polling URL.

Transit:  Seibu Shinjuku Line, Numabukuro → Seibu-Shinjuku
Weather:  Open-Meteo (Nakano, Tokyo) — no API key required
Walk:     9 minutes to Numabukuro station
"""

import csv
import io
import json
import urllib.request
import zipfile
from datetime import datetime, timezone, timedelta

# ── Constants ────────────────────────────────────────────────────────────────

WALK_MINUTES  = 9          # minutes from home to train platform
WALK_TO_BUS   = 4          # minutes from home to bus stop
BUS_RIDE      = 5          # minutes from 哲学堂公園入口 to Nakano Station
SHOW_TRAINS   = 3
SHOW_BUSES    = 3
TIMEZONE      = timezone(timedelta(hours=9))   # JST

# Nakano, Tokyo
LAT = 35.7074
LON = 139.6640

# ── Timetable ────────────────────────────────────────────────────────────────
# Numabukuro → Seibu-Shinjuku (Local, Platform 1, toward Shinjuku)
# Format: (hour, minute)  — 24-hour JST
# Source: Seibu Railway / Navitime (weekday schedule, updated 2025-07)
# NOTE: Seibu runs different schedules on weekdays vs weekends.
# This is the WEEKDAY schedule. Weekend schedule is appended below.
# You should verify and update these periodically at:
# https://www.seiburailway.jp/railways/tourist/english/ride/timetable/

WEEKDAY = [
    # Early morning
    (5, 37), (5, 46),
    # 6am
    (6,  2), (6, 18), (6, 35), (6, 50),
    # 7am — peak, more trains
    (7,  4), (7, 10), (7, 19), (7, 29), (7, 37), (7, 46), (7, 55),
    # 8am — peak
    (8,  3), (8, 10), (8, 17), (8, 24), (8, 31), (8, 39), (8, 47), (8, 55),
    # 9am
    (9,  4), (9, 14), (9, 24), (9, 34), (9, 45), (9, 55),
    # 10am–4pm daytime (~every 10 min)
    (10,  5), (10, 15), (10, 25), (10, 35), (10, 45), (10, 55),
    (11,  5), (11, 15), (11, 25), (11, 35), (11, 45), (11, 55),
    (12,  5), (12, 15), (12, 25), (12, 35), (12, 45), (12, 55),
    (13,  5), (13, 15), (13, 25), (13, 35), (13, 45), (13, 55),
    (14,  5), (14, 15), (14, 25), (14, 35), (14, 45), (14, 55),
    (15,  5), (15, 15), (15, 25), (15, 35), (15, 45), (15, 55),
    (16,  5), (16, 15), (16, 25), (16, 35), (16, 46), (16, 56),
    # 5pm–8pm — evening peak
    (17,  3), (17, 11), (17, 20), (17, 29), (17, 37), (17, 45), (17, 53),
    (18,  1), (18,  9), (18, 17), (18, 25), (18, 33), (18, 41), (18, 50), (18, 59),
    (19,  7), (19, 16), (19, 25), (19, 34), (19, 43), (19, 52),
    (20,  1), (20, 11), (20, 21), (20, 31), (20, 41), (20, 51),
    # 9pm–last train
    (21,  1), (21, 13), (21, 25), (21, 37), (21, 49),
    (22,  1), (22, 13), (22, 25), (22, 37), (22, 50),
    (23,  3), (23, 17), (23, 31), (23, 47),
]

WEEKEND = [
    # Early morning
    (5, 40), (5, 55),
    # 6am
    (6, 10), (6, 25), (6, 40), (6, 55),
    # 7am–9am (less frequent than weekday)
    (7, 10), (7, 25), (7, 40), (7, 55),
    (8, 10), (8, 25), (8, 40), (8, 55),
    (9,  5), (9, 15), (9, 25), (9, 35), (9, 45), (9, 55),
    # 10am–4pm daytime
    (10,  5), (10, 15), (10, 25), (10, 35), (10, 45), (10, 55),
    (11,  5), (11, 15), (11, 25), (11, 35), (11, 45), (11, 55),
    (12,  5), (12, 15), (12, 25), (12, 35), (12, 45), (12, 55),
    (13,  5), (13, 15), (13, 25), (13, 35), (13, 45), (13, 55),
    (14,  5), (14, 15), (14, 25), (14, 35), (14, 45), (14, 55),
    (15,  5), (15, 15), (15, 25), (15, 35), (15, 45), (15, 55),
    (16,  5), (16, 15), (16, 25), (16, 35), (16, 45), (16, 55),
    # Evening
    (17,  5), (17, 15), (17, 25), (17, 35), (17, 45), (17, 55),
    (18,  5), (18, 15), (18, 25), (18, 35), (18, 46), (18, 58),
    (19,  9), (19, 21), (19, 33), (19, 45), (19, 57),
    (20,  9), (20, 22), (20, 35), (20, 48),
    (21,  1), (21, 15), (21, 29), (21, 43), (21, 57),
    (22, 11), (22, 25), (22, 40), (22, 55),
    (23, 10), (23, 25), (23, 40), (23, 55),
]

GTFS_URL      = "https://api.odpt.org/api/v4/files/odpt/KantoBus/AllLines.zip?date=20260507"
BUS_STOP_NAME = "下田橋"
# Routes from 哲学堂公園入口 that go toward Nakano Station (southbound)
BUS_NAKANO_ROUTES = {"中10", "中12", "中20", "中24", "中27", "中30", "中41", "中43", "池11",
                     "10", "12", "20", "24", "27", "30", "41", "43"}

# ── Helpers ──────────────────────────────────────────────────────────────────

def get_schedule(now: datetime) -> list:
    """Return weekday or weekend schedule based on day of week."""
    # weekday() → 0=Mon … 4=Fri, 5=Sat, 6=Sun
    return WEEKDAY if now.weekday() < 5 else WEEKEND


def fmt_mins(m: int) -> str:
    if m < 60:
        return f"{m} min"
    h, rem = divmod(m, 60)
    return f"{h}h {rem}m" if rem else f"{h}h"


def ordinal(n: int) -> str:
    if 11 <= n <= 13:
        return "th"
    return ["th", "st", "nd", "rd", "th"][min(n % 10, 4)]


def fmt_leave_time(dep_min: int, walk: int) -> str:
    """Return 'leave by H:MMam/pm' for the minute you need to leave home."""
    leave_min = (dep_min - walk) % (24 * 60)
    h, m = divmod(leave_min, 60)
    suffix = "am" if h < 12 else "pm"
    hour   = h % 12 or 12
    return f"leave by {hour}:{m:02d}{suffix}"


def fmt_time_short(dep_min: int, walk: int) -> str:
    """Return just 'H:MMam/pm' without the 'leave by' prefix."""
    leave_min = (dep_min - walk) % (24 * 60)
    h, m = divmod(leave_min, 60)
    suffix = "am" if h < 12 else "pm"
    hour   = h % 12 or 12
    return f"{hour}:{m:02d}{suffix}"


def next_trains(now: datetime, count: int = SHOW_TRAINS) -> list:
    """
    Return the next `count` departures from Numabukuro.
    Each entry includes pre-formatted display strings for the Liquid template.
    Travel time Numabukuro → Seibu-Shinjuku ≈ 12 minutes.
    """
    schedule = get_schedule(now)
    now_min  = now.hour * 60 + now.minute

    results = []
    for (h, m) in schedule:
        dep_min = h * 60 + m
        # handle wrap past midnight for very late schedules
        if dep_min < now_min - 2:   # 2-min grace for "just missed"
            continue
        mins_until = dep_min - now_min
        leave_in   = mins_until - WALK_MINUTES
        arr_min    = dep_min + 12   # 12-min ride
        arr_h, arr_m = divmod(arr_min % (24 * 60), 60)

        if leave_in <= 0:
            leave_display = "Leave NOW" if mins_until > 0 else "Train departed"
        else:
            leave_display = fmt_leave_time(dep_min, WALK_MINUTES)

        results.append({
            "departs":              f"{h:02d}:{m:02d}",
            "arrive_shinjuku":      f"{arr_h:02d}:{arr_m:02d}",
            "minutes_until_depart": mins_until,
            "leave_home_in":        leave_in,
            "catchable":            leave_in >= 0,
            "leave_display":        leave_display,
            "next_display":         fmt_leave_time(dep_min, WALK_MINUTES) if leave_in > 0 else "",
            "time_short":           fmt_time_short(dep_min, WALK_MINUTES),
        })
        if len(results) == count:
            break

    return results


def next_buses(now: datetime, api_key: str, count: int = SHOW_BUSES) -> list:
    # Download Kanto Bus GTFS zip
    url = f"{GTFS_URL}&acl:consumerKey={api_key}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; TRMNL-Dashboard/1.0)",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        zf = zipfile.ZipFile(io.BytesIO(r.read()))

    def read_csv(name):
        with zf.open(name) as f:
            return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))

    # Find stop_ids — print all stops with 哲学 to find the right name
    all_stops = read_csv("stops.txt")
    matches = [r for r in all_stops if "下田橋" in r.get("stop_name","")]
    print(f"Stops containing 下田橋: {[(r['stop_id'], r['stop_name']) for r in matches]}")
    stop_ids = {r["stop_id"] for r in matches}
    print(f"Using stop IDs: {stop_ids}")

    # Determine valid services for today
    today    = now.strftime("%Y%m%d")
    day_col  = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"][now.weekday()]
    services = {r["service_id"] for r in read_csv("calendar.txt")
                if r.get(day_col) == "1"
                and r.get("start_date","") <= today <= r.get("end_date","")}
    try:
        for r in read_csv("calendar_dates.txt"):
            if r.get("date") == today:
                if r.get("exception_type") == "1":
                    services.add(r["service_id"])
                elif r.get("exception_type") == "2":
                    services.discard(r["service_id"])
    except KeyError:
        pass

    # Build trip_id → route_short_name map
    routes_map = {r["route_id"]: r.get("route_short_name", r["route_id"])
                  for r in read_csv("routes.txt")}
    trip_route = {}
    for r in read_csv("trips.txt"):
        if r["service_id"] in services and "中野" in r.get("trip_headsign", ""):
            trip_route[r["trip_id"]] = routes_map.get(r["route_id"], "")
    trips = set(trip_route.keys())
    print(f"Valid southbound trips today: {len(trips)}")

    # Get departure times + route numbers from our stop
    now_min   = now.hour * 60 + now.minute
    dep_items = {}  # dep_min → route_short_name
    for r in read_csv("stop_times.txt"):
        if r["stop_id"] in stop_ids and r["trip_id"] in trips:
            t = r.get("departure_time") or r.get("arrival_time","")
            if t:
                h, m = int(t.split(":")[0]), int(t.split(":")[1])
                dep_min = h * 60 + m
                dep_items[dep_min] = trip_route.get(r["trip_id"], "")

    dep_mins = sorted(dep_items.keys())
    print(f"Departures found: {len(dep_mins)}")

    results = []
    for dep_min in dep_mins:
        if dep_min < now_min - 2:
            continue
        mins_until = dep_min - now_min
        leave_in   = mins_until - WALK_TO_BUS
        route      = dep_items.get(dep_min, "")
        route_tag  = f" ({route})" if route else ""
        if leave_in <= 0:
            leave_display = "Leave NOW" if mins_until > 0 else "Bus departed"
        else:
            leave_display = fmt_leave_time(dep_min, WALK_TO_BUS) + route_tag
        results.append({
            "departs":              f"{dep_min//60:02d}:{dep_min%60:02d}",
            "minutes_until_depart": mins_until,
            "leave_home_in":        leave_in,
            "catchable":            leave_in >= 0,
            "leave_display":        leave_display,
            "next_display":         fmt_leave_time(dep_min, WALK_TO_BUS) if leave_in > 0 else "",
            "time_short":           fmt_time_short(dep_min, WALK_TO_BUS) + route_tag,
        })
        if len(results) == count:
            break

    return results


def fetch_weather(lat: float, lon: float) -> dict:
    """
    Fetch current conditions + today's high/low from Open-Meteo.
    No API key required.
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,apparent_temperature,weathercode,"
        f"windspeed_10m,precipitation,relative_humidity_2m"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
        f"weathercode,precipitation_probability_max"
        f"&timezone=Asia%2FTokyo"
        f"&forecast_days=1"
    )
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read())

    cur   = data["current"]
    daily = data["daily"]

    wmo_descriptions = {
        0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Icy fog",
        51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
        61: "Light rain", 63: "Rain", 65: "Heavy rain",
        71: "Light snow", 73: "Snow", 75: "Heavy snow",
        80: "Showers", 81: "Showers", 82: "Heavy showers",
        95: "Thunderstorm", 96: "Thunderstorm+hail", 99: "Thunderstorm+hail",
    }
    wmo_icons = {
        0: "☀️", 1: "🌤", 2: "⛅", 3: "☁️",
        45: "🌫", 48: "🌫",
        51: "🌦", 53: "🌦", 55: "🌧",
        61: "🌧", 63: "🌧", 65: "🌧",
        71: "🌨", 73: "🌨", 75: "🌨",
        80: "🌦", 81: "🌦", 82: "🌧",
        95: "⛈", 96: "⛈", 99: "⛈",
    }
    # umbrella advisory
    precip = cur.get("precipitation", 0) or 0
    daily_precip = (daily.get("precipitation_sum") or [0])[0] or 0
    umbrella = precip > 0.1 or daily_precip > 1.0

    code = cur.get("weathercode", 0)

    return {
        "temp_c":        round(cur["temperature_2m"]),
        "feels_like_c":  round(cur["apparent_temperature"]),
        "humidity_pct":  round(cur["relative_humidity_2m"]),
        "wind_kmh":      round(cur["windspeed_10m"]),
        "description":   wmo_descriptions.get(code, "Unknown"),
        "icon":          wmo_icons.get(code, "🌡"),
        "high_c":        round((daily["temperature_2m_max"] or [0])[0]),
        "low_c":         round((daily["temperature_2m_min"] or [0])[0]),
        "umbrella":      umbrella,
        "precip_mm":     round(daily_precip, 1),
        "rain_pct":      round((daily.get("precipitation_probability_max") or [0])[0] or 0),
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    now = datetime.now(TIMEZONE)

    import os
    odpt_key = os.environ.get("ODPT_API_KEY")

    trains  = next_trains(now)
    buses   = next_buses(now, odpt_key) if odpt_key else []
    weather = fetch_weather(LAT, LON)

    day_names = ["MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY","SATURDAY","SUNDAY"]
    month_names = ["JANUARY","FEBRUARY","MARCH","APRIL","MAY","JUNE",
                   "JULY","AUGUST","SEPTEMBER","OCTOBER","NOVEMBER","DECEMBER"]

    date_main    = f"{day_names[now.weekday()]}, {month_names[now.month - 1]} {now.day}"
    date_ordinal = ordinal(now.day)
    last_update  = fmt_time_short(now.hour * 60 + now.minute, 0)

    def t(i, field):
        return trains[i][field] if len(trains) > i else ""
    def b(i, field):
        return buses[i][field] if len(buses) > i else ""

    payload = {
        "date_main":      date_main,
        "date_ordinal":   date_ordinal,
        "last_update":    last_update,
        "train_display":  t(0, "leave_display") or "No more trains",
        "train_time2":    t(1, "time_short"),
        "train_time3":    t(2, "time_short"),
        "bus_display":    b(0, "leave_display") or "No more buses",
        "bus_time2":      b(1, "time_short"),
        "bus_time3":      b(2, "time_short"),
        "temp_c":         weather["temp_c"],
        "feels_like_c":   weather["feels_like_c"],
        "high_c":         weather["high_c"],
        "low_c":          weather["low_c"],
        "humidity_pct":   weather["humidity_pct"],
        "rain_pct":       weather["rain_pct"],
        "weather_icon":   "☂" if weather["umbrella"] else "☀",
        "weather_label":  "BRING" if weather["umbrella"] else "ENJOY",
    }

    webhook_url = os.environ.get("TRMNL_WEBHOOK_URL")
    if webhook_url:
        body = json.dumps({"merge_variables": payload}).encode()
        print(f"Posting {len(body)} bytes to {webhook_url[:50]}...")
        req  = urllib.request.Request(
            webhook_url, data=body, method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Agent":   "Mozilla/5.0 (compatible; TRMNL-Dashboard/1.0)",
            },
        )
        try:
            with urllib.request.urlopen(req) as r:
                print(f"✓ Pushed to TRMNL: {r.status} — {payload['train_display']}")
        except urllib.error.HTTPError as e:
            print(f"✗ HTTP {e.code}: {e.reason}")
            print(e.read().decode())
    else:
        with open("api/data.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"✓ Written to data.json — {payload['train_display']}")


if __name__ == "__main__":
    main()
