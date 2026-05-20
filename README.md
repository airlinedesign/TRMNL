# TRMNL Tokyo Dashboard

**Seibu Shinjuku Line departures from Numabukuro + Nakano weather — on your e-ink display.**

Displays:
- "Leave in X minutes" countdown to catch the next train
- Next 4 departures with arrival times at Seibu-Shinjuku
- Current weather, high/low, humidity, wind, umbrella advisory

---

## How it works

```
GitHub Actions (every 5 min)
  → runs api/generate.py
  → fetches weather from Open-Meteo (no key needed)
  → computes next trains from baked timetable
  → writes api/data.json
  → pushes to GitHub Pages

TRMNL polls your GitHub Pages URL (every 5 min)
  → merges JSON into Liquid template
  → renders to e-ink display
```

---

## Setup

### 1. Fork / create this repo on GitHub

Make it **public** (required for free GitHub Pages hosting).

### 2. Enable GitHub Pages

Settings → Pages → Source: **Deploy from a branch** → Branch: `main` → Folder: `/ (root)`

After saving, your data URL will be:
```
https://<YOUR_USERNAME>.github.io/<REPO_NAME>/api/data.json
```

Test it by visiting that URL after the first Action run.

### 3. Enable GitHub Actions

Go to Actions tab → Enable workflows if prompted.
Trigger a manual run: Actions → "Generate TRMNL Dashboard Data" → Run workflow.

Check that `api/data.json` appeared and was pushed to the repo.

### 4. Create a TRMNL Private Plugin

In your TRMNL dashboard:

1. Go to **Plugins → Private Plugin → New Plugin**
2. Name it: `Tokyo Transit`
3. **Polling URL**: `https://<YOUR_USERNAME>.github.io/<REPO_NAME>/api/data.json`
4. **Refresh frequency**: `300` (5 minutes)
5. Save

Then click **Edit Markup**, paste the full contents of `trmnl-markup-full.liquid`, and save.

### 5. Add to your playlist

Add the plugin to your TRMNL playlist and set it as active.

---

## Customisation

### Walk time
Edit `WALK_MINUTES` at the top of `api/generate.py`. Currently set to `9` minutes.

### Timetable accuracy
The timetable in `generate.py` is based on the Seibu Railway weekday/weekend schedule
as of July 2025. Seibu occasionally adjusts schedules (typically March and December).

Verify and update at:
- https://www.seiburailway.jp/railways/tourist/english/ride/timetable/
- https://japantravel.navitime.com/en/area/jp/timetable/00003886/00000721?direction=up

### Number of trains shown
Change `SHOW_TRAINS = 4` in `generate.py`.

### Weather location
The coordinates in `generate.py` are set to Nakano (35.7074, 139.6640).
Adjust `LAT` / `LON` if needed.

---

## Timetable note

Numabukuro only stops **Local** trains toward Seibu-Shinjuku.
Express / Semi-Express trains skip this station.
Travel time to Seibu-Shinjuku: ~12 minutes.

---

## Files

| File | Purpose |
|---|---|
| `api/generate.py` | Data generator (train logic + weather fetch) |
| `api/data.json` | Generated output — TRMNL polls this URL |
| `.github/workflows/generate.yml` | GitHub Actions schedule (every 5 min) |
| `trmnl-markup-full.liquid` | Paste this into TRMNL markup editor |
