"""
TRMNL Tokyo Dashboard — data generator
Runs via GitHub Actions on a schedule, writes api/data.json
which TRMNL polls as the plugin's Polling URL.

Transit:  Seibu Shinjuku Line, Numabukuro → Seibu-Shinjuku
Weather:  Open-Meteo (Nakano, Tokyo) — no API key required
Walk:     9 minutes to Numabukuro station
"""

import json
import urllib.request
from datetime import datetime, timezone, timedelta

# ── Constants ────────────────────────────────────────────────────────────────

WALK_MINUTES  = 9          # minutes from home to train platform
WALK_TO_BUS   = 4          # minutes from home to bus stop
BUS_RIDE      = 5          # minutes from 哲学堂公園入口 to Nakano Station
SHOW_TRAINS   = 2
SHOW_BUSES    = 2
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

# ── Bus timetable ─────────────────────────────────────────────────────────────
# 関東バス 中12 — 哲学堂公園入口 → 中野駅 (southbound on Nakano Dori)
# Source: ekitan.com (weekday schedule, verified 2025-07)
# TODO: add actual weekend schedule; using weekday as placeholder
BUS_12_WEEKDAY = [
    (6, 42),
    (7,  1), (7, 19), (7, 32), (7, 42), (7, 55),
    (8,  7), (8, 19), (8, 32), (8, 45), (8, 58),
    (9, 12), (9, 26), (9, 47),
    (10,  8), (10, 31), (10, 57),
    (11, 23), (11, 49),
    (12, 15), (12, 41),
    (13,  7), (13, 33),
    (14,  0), (14, 27), (14, 54),
    (15, 18), (15, 42),
    (16,  6), (16, 30), (16, 54),
    (17, 18), (17, 42),
    (18,  6), (18, 30), (18, 54),
    (19, 18), (19, 42),
    (20,  7), (20, 37),
    (21,  7), (21, 52),
]
BUS_12_WEEKEND = BUS_12_WEEKDAY  # placeholder until ODPT key available

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


def fmt_leave_time(dep_min: int, walk: int) -> str:
    """Return 'leave by H:MMam/pm' for the minute you need to leave home."""
    leave_min = (dep_min - walk) % (24 * 60)
    h, m = divmod(leave_min, 60)
    suffix = "am" if h < 12 else "pm"
    hour   = h % 12 or 12
    return f"leave by {hour}:{m:02d}{suffix}"


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
        })
        if len(results) == count:
            break

    return results


def next_buses(now: datetime, count: int = SHOW_BUSES) -> list:
    schedule = BUS_12_WEEKDAY if now.weekday() < 5 else BUS_12_WEEKEND
    now_min  = now.hour * 60 + now.minute

    results = []
    for (h, m) in schedule:
        dep_min = h * 60 + m
        if dep_min < now_min - 2:
            continue
        mins_until = dep_min - now_min
        leave_in   = mins_until - WALK_TO_BUS
        arr_min    = dep_min + BUS_RIDE
        arr_h, arr_m = divmod(arr_min % (24 * 60), 60)

        if leave_in <= 0:
            leave_display = "Leave NOW" if mins_until > 0 else "Bus departed"
        else:
            leave_display = fmt_leave_time(dep_min, WALK_TO_BUS)

        results.append({
            "departs":              f"{h:02d}:{m:02d}",
            "arrive_nakano":        f"{arr_h:02d}:{arr_m:02d}",
            "minutes_until_depart": mins_until,
            "leave_home_in":        leave_in,
            "catchable":            leave_in >= 0,
            "leave_display":        leave_display,
            "next_display":         fmt_leave_time(dep_min, WALK_TO_BUS) if leave_in > 0 else "",
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
        f"weathercode"
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
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    now = datetime.now(TIMEZONE)

    trains  = next_trains(now)
    buses   = next_buses(now)
    weather = fetch_weather(LAT, LON)

    next_t = trains[0] if trains else None
    if next_t:
        if next_t["leave_home_in"] <= 0:
            headline = "Leave NOW" if next_t["minutes_until_depart"] > 0 else "Train departed"
        else:
            headline = next_t["leave_display"]
    else:
        headline = "No more trains today"

    day_type = "Weekday" if now.weekday() < 5 else "Weekend"

    payload = {
        "generated_at":   now.strftime("%H:%M JST"),
        "day_type":       day_type,
        "train_display":  trains[0]["leave_display"] if trains else "No more trains",
        "train_next":     trains[1]["next_display"]  if len(trains) > 1 else "",
        "bus_display":    buses[0]["leave_display"]  if buses else "No more buses",
        "bus_next":       buses[1]["next_display"]   if len(buses) > 1 else "",
        "temp_c":         weather["temp_c"],
        "feels_like_c":   weather["feels_like_c"],
        "description":    weather["description"],
        "high_c":         weather["high_c"],
        "low_c":          weather["low_c"],
        "humidity_pct":   weather["humidity_pct"],
        "weather_icon":   "☂" if weather["umbrella"] else "🎩",
    }

    import os
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
