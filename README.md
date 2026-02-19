# TPG Collector Tool

A two-script toolkit for running TPG spinoffs — generates Discord round announcements and processes player coordinate submissions.

---

## Prerequisites

**Python 3.8+** is required. Install dependencies with:

```bash
pip install pandas geopy simplekml python-dateutil
```

If you're on Python 3.8, also install:

```bash
pip install backports.zoneinfo
```

---

## File Structure

Place all files in the same folder before running:

```
TPG Collector Tool/
├── 1_prep_round.py        # Run first — sets up a new round
├── 2_collect_subs.py      # Run second — processes submissions
├── config.txt             # Your links, timezone, and display settings
├── submissions.txt        # Paste Discord submissions here before running Step 2
├── aliases.csv            # Auto-generated — maps Discord usernames to display names
├── roundlist.csv          # Auto-generated — tracks all rounds and player coordinates
└── Rounds/                # Auto-generated — one subfolder per round
    └── Round 1/
        ├── Round 1.csv    # Submissions and distances for the round
        └── Round 1.kml    # Google Earth/Maps pin file for the round
```

---

## Setup: config.txt

Before your first round, edit `config.txt` with your own links and timezone:

```
SUBMISSION_TRACKER_URL = https://...
LEADERBOARD_URL        = https://...
RULES_URL              = https://...         # Leave blank to omit from message

SUBMISSION_TRACKER_LABEL = Submission Tracker
LEADERBOARD_LABEL        = Leaderboard
RULES_LABEL              = Rules

TIMEZONE = America/New_York
```

The timezone controls how round end times are interpreted. Discord will automatically convert the timestamp to each viewer's local time. Common values: `America/Chicago`, `America/Los_Angeles`, `Europe/London`, `UTC`.

---

## Step 1 — Prep Round (`1_prep_round.py`)

Run this once per round **before** opening submissions.

```bash
python 1_prep_round.py
```

You'll be prompted for:

| Prompt | Example |
|---|---|
| Round Number | `5 ` (Note: "Round" will be automatically added before the number) | 
| Location Name | `Ohio, United States of America` |
| Country Code | `US` (Note: see https://emojipedia.org/flags)| 
| Coordinates | `40.001667, -83.019722` |
| Round End Time | `9:30 PM` or `February 20, 2026 at 10:30 AM` (Note: defaults to current date) | 

**What it does:**
- Creates `Rounds/Round N/Round N.csv` with the target location
- Adds the round column to `roundlist.csv`
- Prints a formatted Discord message (with flag emoji, Google Maps link, and Discord timestamp) ready to copy and paste

---

## Step 2 — Collect Submissions (`2_collect_subs.py`)

Run this after the round closes or to collect submissions during a round.

**First:** Copy the raw text from your Discord submissions channel and paste it into `submissions.txt`, then save.

```bash
python 2_collect_subs.py
```

You'll be prompted for:

| Prompt | Example |
|---|---|
| Round name | `Round 5` |

For each detected submission, you'll see:

```
------------------------------
REVIEWING: PlayerName (NEW PLAYER) (User: discord_username)
MESSAGE: 1.23456, -1.23456 Test Land
COORDS: 1.23456, -1.23456
Approve? [y/n]:
```

- Enter `y` to approve, `n` to skip
- If a username hasn't been seen before, you'll be asked for their display alias once — it's saved to `aliases.csv` for future rounds. This is how it will be displayed on the KML tracker
- New players are added to `roundlist.csv` automatically

**What it does:**
- Parses coordinates from free-form submission messages (supports decimal, DMS, and hybrid formats)
- Calculates great-circle distance from each player to the target location in miles and km
- Sorts players by distance in the round CSV
- Generates a `.kml` file you can import into Google MyMaps or Google Earth to visualize all pins

---

## Notes

- Run `1_prep_round.py` before `2_collect_subs.py` — the collect script will exit if the round hasn't been initialized
- You can re-run `2_collect_subs.py` to add late submissions; existing entries will be replaced rather than duplicated
- `aliases.csv` persists across rounds — a player's username only needs to be mapped once
- The `submissions.txt` file is not cleared automatically — replace its contents each round
