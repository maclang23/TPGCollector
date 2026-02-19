import re
import os
import csv
import pandas as pd
from geopy.distance import great_circle
import simplekml

# -------------------------------
# --- Helper: Alias & Roster ---
# -------------------------------
aliases_file = "aliases.csv"
aliases = {}

if os.path.exists(aliases_file):
    with open(aliases_file, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            aliases[row['Username']] = row['Alias']
else:
    with open(aliases_file, 'w', newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=['Username', 'Alias'])
        writer.writeheader()

def get_alias(username):
    username = username.strip()
    if username in aliases:
        return aliases[username]
    else:
        alias = input(f"Enter alias for username '{username}': ").strip()
        aliases[username] = alias
        with open(aliases_file, 'a', newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=['Username', 'Alias'])
            writer.writerow({'Username': username, 'Alias': alias})
        return alias

# -------------------------------
# --- Helper: Coordinates ---
# -------------------------------
def dms_to_decimal(degrees, minutes=0, seconds=0, direction=None):
    d, m, s = float(degrees or 0), float(minutes or 0), float(seconds or 0)
    dec = d + (m / 60.0) + (s / 3600.0)
    if direction and direction.upper() in ['S', 'W']:
        dec = -abs(dec)
    return dec

def parse_coordinates(text):
    text = re.sub(r'(?i)forwarded', '', text).strip()

    dms_full_regex = re.compile(
        r'(\d+)\s*°\s*(\d+)\s*[\'′]\s*(\d+(?:\.\d+)?)\s*["″]?\s*([NS])'
        r'[\s,]+'
        r'(\d+)\s*°\s*(\d+)\s*[\'′]\s*(\d+(?:\.\d+)?)\s*["″]?\s*([EW])',
        re.I
    )
    m_full = dms_full_regex.search(text)
    if m_full:
        lat_d, lat_m, lat_s, lat_dir, lon_d, lon_m, lon_s, lon_dir = m_full.groups()
        return dms_to_decimal(lat_d, lat_m, lat_s, lat_dir), dms_to_decimal(lon_d, lon_m, lon_s, lon_dir)

    dms_hybrid_regex = re.compile(r'(\d+(?:\.\d+)?)\s*°\s*([NS])[\s,]+(\d+(?:\.\d+)?)\s*°\s*([EW])', re.I)
    m_hyb = dms_hybrid_regex.search(text)
    if m_hyb:
        lat, lat_dir, lon, lon_dir = m_hyb.groups()
        return dms_to_decimal(lat, direction=lat_dir), dms_to_decimal(lon, direction=lon_dir)

    dec_regex = re.compile(r'(-?\d+\.\d+)\s*°?\s*([NS]\b)?,?\s*(-?\d+\.\d+)\s*°?\s*([EW]\b)?', re.I)
    m_dec = dec_regex.search(text)
    if m_dec:
        lat_val, lat_dir, lon_val, lon_dir = m_dec.groups()
        lat, lon = float(lat_val), float(lon_val)
        if lat_dir and lon_dir:
            if lat_dir.upper() == 'S': lat = -abs(lat)
            if lon_dir.upper() == 'W': lon = -abs(lon)
        return lat, lon
    return None, None

# -------------------------------
# --- Helper: Discord Parsing ---
# -------------------------------
def clean_discord_text(raw_file):
    if not os.path.exists(raw_file):
        return []
    with open(raw_file, "r", encoding="utf-8") as f:
        raw_lines = [line.strip().replace('\xa0', ' ') for line in f]

    submissions = []
    current_user, current_msg = None, []

    header_trigger = re.compile(r'(Role icon|Yesterday at|Today at|— \d{1,2}/\d{1,2}/\d{2,4})', re.I)

    for i in range(len(raw_lines)):
        line = raw_lines[i]
        if not line:
            continue

        if header_trigger.search(line):
            name_part = re.split(r'—', line)[0].strip()
            potential_user = re.split(r'Role icon|Sapphire|Diamond|Ruby|Gold|Silver|Bronze|TPG Fanatic', name_part, flags=re.I)[0].strip()
            potential_user = re.sub(r'<a?:\w+:\d+>|:\w+:', '', potential_user)
            potential_user = potential_user.rstrip(',').strip()

            if not potential_user:
                for j in range(i - 1, -1, -1):
                    prev = raw_lines[j]
                    if prev and not header_trigger.search(prev) and prev not in ["Forwarded", "Image"]:
                        potential_user = re.sub(r'<a?:\w+:\d+>|:\w+:', '', prev).strip()
                        break

            if potential_user and potential_user not in ["Forwarded", "Image"]:
                if current_user and current_msg:
                    submissions.append({"user": current_user, "msg": " ".join(current_msg)})
                current_user = potential_user
                current_msg = []
                continue

        if current_user:
            if line not in ["Forwarded", "Image"]:
                current_msg.append(line)

    if current_user and current_msg:
        submissions.append({"user": current_user, "msg": " ".join(current_msg)})

    return submissions

# -------------------------------
# --- Main Logic ---
# -------------------------------
def load_csv_clean(path, default_columns):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        try:
            return pd.read_csv(path)
        except pd.errors.EmptyDataError:
            pass
    return pd.DataFrame(columns=default_columns)

round_df = load_csv_clean("roundlist.csv", ["Name"])

round_name = input("Enter current round name (e.g., Round 1): ").strip()
round_csv_path = os.path.join("Rounds", round_name, f"{round_name}.csv")

if round_name not in round_df.columns or not os.path.exists(round_csv_path):
    print(f"\n{round_name} not initialized.")
    exit()

round_sub_df = pd.read_csv(round_csv_path)
raw_data = clean_discord_text("submissions.txt")

for item in raw_data:
    alias = get_alias(item['user'])
    lat, lon = parse_coordinates(item['msg'])
    if lat is None:
        continue

    is_new_player = alias not in round_df["Name"].values

    print("-" * 30)
    print(f"REVIEWING: {alias}{' (NEW PLAYER)' if is_new_player else ''} (User: {item['user']})")
    print(f"MESSAGE: {item['msg']}")
    print(f"COORDS: {lat}, {lon}")

    if input("Approve? [y/n]: ").lower() == 'y':
        parsed_coords = f"{lat},{lon}"

        if is_new_player:
            new_r = pd.DataFrame([{col: (alias if col == "Name" else "") for col in round_df.columns}])
            round_df = pd.concat([round_df, new_r], ignore_index=True)

        round_df.loc[round_df["Name"] == alias, round_name] = parsed_coords

        if alias in round_sub_df["Name"].values:
            round_sub_df.loc[round_sub_df["Name"] == alias, "Coordinates"] = parsed_coords
        else:
            new_sub = pd.DataFrame([{
                "Name": alias,
                "Coordinates": parsed_coords,
                "Distance (mi)": "",
                "Distance (km)": ""
            }])
            round_sub_df = pd.concat([round_sub_df, new_sub], ignore_index=True)

# -------------------------------
# --- Distance Calculation ---
# -------------------------------
try:
    target_coords = tuple(map(float, round_sub_df.iloc[0]["Coordinates"].split(",")))
    for i in range(1, len(round_sub_df)):
        coords_str = round_sub_df.at[i, "Coordinates"]
        if not coords_str or str(coords_str).strip() == "":
            continue
        p_coords = tuple(map(float, str(coords_str).split(",")))
        d = great_circle(target_coords, p_coords)
        round_sub_df.at[i, "Distance (mi)"] = round(d.miles, 2)
        round_sub_df.at[i, "Distance (km)"] = round(d.kilometers, 4)
except Exception as e:
    print(f"Distance calculation error: {e}")

# -------------------------------
# --- Sort by Distance ---
# -------------------------------
try:
    header = round_sub_df.iloc[[0]]
    players = round_sub_df.iloc[1:].copy()
    players = players[players["Distance (mi)"] != ""].sort_values(by="Distance (mi)")
    round_sub_df = pd.concat([header, players])
except Exception as e:
    print(f"Sort error: {e}")

# -------------------------------
# --- Save Results ---
# -------------------------------
round_sub_df.to_csv(round_csv_path, index=False)
round_df.to_csv("roundlist.csv", index=False)
print(f"\nSubmissions saved to {round_csv_path}")
print("roundlist.csv updated.")

# -------------------------------
# --- KML Generation ---
# -------------------------------
try:
    kml = simplekml.Kml()
    target_coords = tuple(map(float, round_sub_df.iloc[0]["Coordinates"].split(",")))

    tp = kml.newpoint(name="LOCATION", coords=[(target_coords[1], target_coords[0])])
    tp.style.iconstyle.color = simplekml.Color.blue

    for _, row in round_sub_df.iloc[1:].iterrows():
        coords_str = str(row["Coordinates"]).strip()
        if not coords_str:
            continue
        plat, plon = map(float, coords_str.split(","))
        pnt = kml.newpoint(name=row["Name"], coords=[(plon, plat)])
        pnt.description = (
            f"Coordinates: {plat}, {plon}\n"
            f"Distance: {row['Distance (mi)']} mi / {row['Distance (km)']} km"
        )
        pnt.style.iconstyle.color = simplekml.Color.blue

    kml_path = os.path.join("Rounds", round_name, f"{round_name}.kml")
    kml.save(kml_path)
    print(f"KML saved to {kml_path}")
except Exception as e:
    print(f"KML Error: {e}")
