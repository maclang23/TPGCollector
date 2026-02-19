from datetime import datetime, timedelta, timezone
from dateutil import parser
import urllib.parse
import re
import os
import csv
import pandas as pd
import sys

if sys.version_info < (3, 9):
    from backports.zoneinfo import ZoneInfo
else:
    from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config(config_path="config.txt"):
    """Load key=value pairs from config.txt, ignoring comments and blank lines."""
    config = {}
    if not os.path.exists(config_path):
        print(f"Config file not found at '{config_path}'. Using defaults.")
        return config
    with open(config_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()
    return config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_discord_timestamp(date_str, tz_name="UTC", style="F"):
    """Parse a date/time string and convert it to a Discord timestamp using the configured timezone."""
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        print(f"Unknown timezone '{tz_name}', falling back to UTC.")
        tz = ZoneInfo("UTC")

    dt = parser.parse(date_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    else:
        dt = dt.astimezone(tz)

    utc_dt = dt.astimezone(timezone.utc)
    timestamp = int(utc_dt.timestamp())
    return f"<t:{timestamp}:{style}>"

def country_code_to_emoji(code):
    code = code.upper()
    if len(code) != 2 or not code.isalpha():
        return ""
    return chr(127397 + ord(code[0])) + chr(127397 + ord(code[1]))

def parse_coordinates(coord_line):
    coord_line = coord_line.strip()
    match = re.search(
        r"Latitude:\s*(-?\d+\.?\d*),\s*Longitude:\s*(-?\d+\.?\d*)",
        coord_line, re.IGNORECASE,
    )
    if match:
        return match.group(1), match.group(2)
    match = re.search(r"^\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*$", coord_line)
    if match:
        return match.group(1), match.group(2)
    raise ValueError("Invalid coordinate format.")

# ---------------------------------------------------------------------------
# File / CSV helpers
# ---------------------------------------------------------------------------

def create_round_folder_and_csv(round_name, latitude, longitude):
    base_folder = os.getcwd()
    rounds_folder = os.path.join(base_folder, "Rounds")
    round_folder = os.path.join(rounds_folder, round_name)
    os.makedirs(round_folder, exist_ok=True)
    csv_path = os.path.join(round_folder, f"{round_name}.csv")

    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["Name", "Coordinates", "Distance (mi)", "Distance (km)"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "Name": "LOCATION",
                "Coordinates": f"{latitude},{longitude}",
                "Distance (mi)": 0,
                "Distance (km)": 0,
            }
        )
    print(f"Round folder and CSV created at: {csv_path}")

def update_roundlist(round_number, latitude, longitude):
    base_folder = os.getcwd()
    roundlist_path = os.path.join(base_folder, "roundlist.csv")
    col_name = f"Round {round_number}"
    coords = f"{latitude},{longitude}"

    file_is_empty = not os.path.exists(roundlist_path) or os.path.getsize(roundlist_path) == 0

    if file_is_empty:
        df = pd.DataFrame(columns=["Name", col_name])
        new_row = {"Name": "Location", col_name: coords}
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    else:
        try:
            df = pd.read_csv(roundlist_path)
        except pd.errors.EmptyDataError:
            df = pd.DataFrame(columns=["Name", col_name])
            df = pd.concat([df, pd.DataFrame([{"Name": "Location", col_name: coords}])], ignore_index=True)
            df.to_csv(roundlist_path, index=False)
            print(f"roundlist.csv updated with Location for {col_name}")
            return
        if col_name not in df.columns:
            df[col_name] = ""
        if "Location" in df["Name"].values:
            df.loc[df["Name"] == "Location", col_name] = coords
        else:
            new_row = {col: "" for col in df.columns}
            new_row["Name"] = "Location"
            new_row[col_name] = coords
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    df.to_csv(roundlist_path, index=False)
    print(f"roundlist.csv updated with Location for {col_name}")

# ---------------------------------------------------------------------------
# Main message builder
# ---------------------------------------------------------------------------

def format_round_message(config):
    round_number  = input("Enter Round Number: ").strip()
    location_name = input("Enter Location Name: ").strip()
    country_code  = input("Enter Country Code: ").strip()
    coord_line    = input("Enter Coordinates: ").strip()

    latitude, longitude = parse_coordinates(coord_line)
    flag   = country_code_to_emoji(country_code)
    coords = f"{latitude},{longitude}"
    maps_url = (
        f"https://www.google.com/maps/place/{urllib.parse.quote(coords)}"
        f"/@{latitude},{longitude},14z"
    )

    tz_name  = config.get("TIMEZONE", "UTC").strip() or "UTC"
    end_time = input(f"Enter Round End Time (e.g. 9:30 PM, 21:30, Jan 5 9:30 PM) [{tz_name}]: ").strip()
    timestamp = to_discord_timestamp(end_time, tz_name=tz_name, style="F")

    # --- Build optional link lines ---
    link_lines = []

    def add_link(url_key, label_key, default_label):
        url   = config.get(url_key, "").strip()
        label = config.get(label_key, "").strip() or default_label
        if url:
            link_lines.append(f"[{label}]({url})")

    add_link("SUBMISSION_TRACKER_URL", "SUBMISSION_TRACKER_LABEL", "Submission Tracker")
    add_link("LEADERBOARD_URL",        "LEADERBOARD_LABEL",        "Leaderboard")
    add_link("RULES_URL",              "RULES_LABEL",              "Rules")

    # --- Assemble message ---
    message = (
        f"# Round {round_number}: {location_name} {flag}, "
        f"at [{coords}]({maps_url})\n"
        f"Round ends {timestamp}\n"
    )
    if link_lines:
        message += "\n".join(link_lines) + "\n"

    create_round_folder_and_csv(f"Round {round_number}", latitude, longitude)
    update_roundlist(round_number, latitude, longitude)
    return message

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    config = load_config("config.txt")
    result = format_round_message(config)
    print("\nFormatted Message:\n")
    print(result)
