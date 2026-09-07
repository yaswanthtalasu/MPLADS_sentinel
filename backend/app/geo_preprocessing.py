import os
import json
import re
import requests
import sqlite3
import pandas as pd
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

GEOJSON_URL = "https://raw.githubusercontent.com/datameet/maps/master/parliamentary-constituencies/india_pc_2019_simplified.geojson"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "geo_data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

PC_GEOJSON_PATH = os.path.join(OUTPUT_DIR, "india_constituencies_2019.geojson")
STATE_GEOJSON_PATH = os.path.join(OUTPUT_DIR, "india_states_2019.geojson")
QUALITY_REPORT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "map_data_quality_report.csv")
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "mplads_prototype.db")
DATASET_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "mplads_enriched_prototype_dataset.csv")

# State Normalization Map
STATE_NORM_MAP = {
    "odisha": "orissa",
    "orissa": "orissa",
    "jammu and kashmir": "jammu & kashmir",
    "jammu & kashmir": "jammu & kashmir",
    "andaman and nicobar": "andaman & nicobar",
    "andaman and nicobar islands": "andaman & nicobar",
    "andaman & nicobar": "andaman & nicobar",
    "dadra and nagar haveli": "dadra & nagar haveli",
    "dadra & nagar haveli": "dadra & nagar haveli",
    "daman and diu": "daman & diu",
    "daman & diu": "daman & diu",
    "nct of delhi": "delhi",
    "delhi": "delhi",
    "pondicherry": "puducherry",
    "puducherry": "puducherry",
    "uttaranchal": "uttarakhand",
    "uttarakhand": "uttarakhand",
    "chhatisgarh": "chhattisgarh",
    "chhattisgarh": "chhattisgarh"
}

# Constituency Aliases (state_norm, pc_norm) -> geo_pc_name_norm
PC_ALIASES = {
    # Andhra Pradesh
    ("andhra pradesh", "anakapalle"): "anakapalli",
    ("andhra pradesh", "anantapur"): "anantapuramu",
    ("andhra pradesh", "anantapuramu"): "anantapuramu",
    # Assam (Delimitation adjustments & transliterations)
    ("assam", "guwahati"): "gauhati",
    ("assam", "darrangudalguri"): "mangaldoi",
    ("assam", "diphu"): "autonomous district",
    ("assam", "sonitpur"): "tezpur",
    ("assam", "kaziranga"): "kaliabor",
    # Bihar
    ("bihar", "aurangabadbr"): "aurangabad",
    ("bihar", "maharajganjbr"): "maharajganj",
    ("bihar", "purnea"): "purnia",
    ("bihar", "ujjarpur"): "ujiarpur",
    ("bihar", "samastipur"): "samastipur",
    ("bihar", "madhepura"): "madhepura",
    # Chhattisgarh
    ("chhattisgarh", "janjgirchampa"): "janjgir",
    ("chhattisgarh", "janjgir"): "janjgir",
    ("chhattisgarh", "sarguja"): "surguja",
    # Delhi
    ("delhi", "chandinichowk"): "chandni chowk",
    # Haryana
    ("haryana", "sonepat"): "sonipat",
    # Himachal Pradesh
    ("himachal pradesh", "hamirpurhp"): "hamirpur",
    # Jammu and Kashmir
    ("jammu & kashmir", "baramullah"): "baramulla",
    # Karnataka
    ("karnataka", "belgaum"): "belagavi",
    ("karnataka", "chikkodi"): "chikodi",
    ("karnataka", "chikodi"): "chikodi",
    ("karnataka", "davanagere"): "davangere",
    ("karnataka", "hassan"): "haasan",
    # Kerala
    ("kerala", "chalakkudy"): "chalakudy",
    ("kerala", "mavelikkara"): "mavelikara",
    ("kerala", "mavelikara"): "mavelikara",
    ("kerala", "pathanamthitta"): "pathanamthitta",
    ("kerala", "thiruvananthapuram"): "thiruvananthapuram",
    ("kerala", "alathur"): "alathur",
    ("kerala", "kannur"): "kannur",
    # Madhya Pradesh
    ("madhya pradesh", "khargone"): "khargone",
    ("madhya pradesh", "mandsour"): "mandsaur",
    ("madhya pradesh", "mandsaur"): "mandsaur",
    # Maharashtra
    ("maharashtra", "aurangabad"): "aurangabad",
    ("maharashtra", "aurangabadmh"): "aurangabad",
    ("maharashtra", "ahmednagar"): "ahmednagar",
    ("maharashtra", "mumbaisouthcentral"): "mumbai south central",
    ("maharashtra", "mumbainorthcentral"): "mumbai north central",
    ("maharashtra", "mumbainorthwest"): "mumbai north west",
    ("maharashtra", "mumbainortheast"): "mumbai north east",
    ("maharashtra", "mumbaisouth"): "mumbai south",
    ("maharashtra", "mumbainorth"): "mumbai north",
    ("maharashtra", "amravati"): "amravati",
    ("maharashtra", "buldhana"): "buldhana",
    # Odisha
    ("orissa", "balasore"): "balasore",
    ("orissa", "bhadrak"): "bhadrak",
    ("orissa", "jajpur"): "jajpur",
    ("orissa", "mayurbhanj"): "mayurbhanj",
    ("orissa", "nabarangpur"): "nabarangpur",
    ("orissa", "sambalpur"): "sambalpur",
    ("orissa", "sundergarh"): "sundargarh",
    # Punjab
    ("punjab", "firozpur"): "firozepur",
    ("punjab", "ferozepur"): "firozepur",
    ("punjab", "bhatinda"): "bathinda",
    ("punjab", "bathinda"): "bathinda",
    # Rajasthan
    ("rajasthan", "chittorgarh"): "chittorgarh",
    ("rajasthan", "jhunjhunu"): "jhunjhunu",
    ("rajasthan", "tonksawaimadhopur"): "tonksawaimadhopur",
    # Tamil Nadu
    ("tamil nadu", "sivaganga"): "sivaganga",
    ("tamil nadu", "tenkasi"): "tenkasi",
    ("tamil nadu", "thoothukkudi"): "thoothukudi",
    ("tamil nadu", "thoothukudi"): "thoothukudi",
    ("tamil nadu", "tiruvallur"): "thiruvallur",
    ("tamil nadu", "viluppuram"): "viluppuram",
    ("tamil nadu", "virudhunagar"): "virudhunagar",
    ("tamil nadu", "sriperumbudur"): "sriperumbudur",
    ("tamil nadu", "chidambaram"): "chidambaram",
    ("tamil nadu", "kallakurichi"): "kallakurichi",
    ("tamil nadu", "dharamapuri"): "dharmapuri",
    ("tamil nadu", "dharmapuri"): "dharmapuri",
    ("tamil nadu", "mayiladuthurai"): "mayiladuturai",
    ("tamil nadu", "mayiladuturai"): "mayiladuturai",
    ("tamil nadu", "kanniyakumari"): "kanyakumari",
    ("tamil nadu", "kanyakumari"): "kanyakumari",
    # Telangana
    ("telangana", "chevella"): "chevella",
    ("telangana", "chelvella"): "chevella",
    ("telangana", "bhongir"): "bhuvanagiri",
    ("telangana", "bhuvanagiri"): "bhuvanagiri",
    ("telangana", "warangel"): "warangal",
    ("telangana", "warangal"): "warangal",
    ("telangana", "peddapalle"): "peddapalli",
    ("telangana", "secunderabad"): "secunderabad",
    # Uttarakhand
    ("uttarakhand", "nainitaludhamsinghnag"): "nainitaludhamsingh nagar",
    ("uttarakhand", "nainitaludhamsinghnagar"): "nainitaludhamsingh nagar",
    ("uttarakhand", "hardwar"): "haridwar",
    ("uttarakhand", "haridwar"): "haridwar",
    # Uttar Pradesh
    ("uttar pradesh", "faizabad"): "faizabad",
    ("uttar pradesh", "gautambuddhanagar"): "gautam buddha nagar",
    ("uttar pradesh", "kushi nagar"): "kushinagar",
    ("uttar pradesh", "kushinagar"): "kushinagar",
    ("uttar pradesh", "santkabirnagar"): "sant kabir nagar",
    ("uttar pradesh", "shahjahanpur"): "shahjahanpur",
    ("uttar pradesh", "shrawasti"): "shrawasti",
    ("uttar pradesh", "siddharthnagar"): "domariyaganj",
    ("uttar pradesh", "maharajganjup"): "maharajganj",
    ("uttar pradesh", "hamirpurup"): "hamirpur",
    # West Bengal
    ("west bengal", "bardhaman durgapur"): "bardhaman durgapur",
    ("west bengal", "bardhaman purba"): "bardhaman purba",
    ("west bengal", "medinipur"): "medinipur",
    ("west bengal", "maldaha dakshin"): "maldaha dakshin",
    ("west bengal", "maldaha uttar"): "maldaha uttar",
    ("west bengal", "joynagar"): "jaynagar",
    ("west bengal", "arambag"): "arambagh",
    ("west bengal", "arambagh"): "arambagh",
    ("west bengal", "barrackpur"): "barrackpore",
    ("west bengal", "barrackpore"): "barrackpore",
}

def clean_str(s):
    if not isinstance(s, str):
        return ""
    s = s.strip().lower()
    s = re.sub(r"\s*\((sc|st|gen)\)\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s

def norm_state(s):
    if not isinstance(s, str):
        return ""
    s = s.strip().lower()
    return STATE_NORM_MAP.get(s, s)

def fetch_or_load_pc_geojson():
    if not os.path.exists(PC_GEOJSON_PATH):
        print(f"Downloading official PC GeoJSON from {GEOJSON_URL}...")
        resp = requests.get(GEOJSON_URL, timeout=30)
        resp.raise_for_status()
        with open(PC_GEOJSON_PATH, "wb") as f:
            f.write(resp.content)
        print("Downloaded PC GeoJSON.")
    with open(PC_GEOJSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def run_preprocessing():
    print("=== Starting Geospatial Preprocessing & Entity Resolution ===")
    raw_pc_geo = fetch_or_load_pc_geojson()
    print(f"Loaded {len(raw_pc_geo['features'])} Parliamentary Constituencies from GeoJSON.")

    # 1. Process Geo Features, calculate centroids & bounding boxes
    processed_pc_features = []
    geo_lookup = {} # (norm_state, clean_pc) -> feature_props
    state_polygons = {} # norm_state -> list of shapely geoms
    state_meta = {}

    for feature in raw_pc_geo["features"]:
        props = feature["properties"]
        geom = shape(feature["geometry"])
        centroid = geom.centroid
        bounds = geom.bounds # (minx, miny, maxx, maxy)

        st_name = props.get("st_name", "").strip()
        pc_name = props.get("pc_name", "").strip()
        pc_id = props.get("pc_id")
        pc_no = props.get("pc_no")

        norm_st = norm_state(st_name)
        norm_pc = clean_str(pc_name)

        props_enriched = {
            "pc_id": pc_id,
            "pc_no": pc_no,
            "pc_name": pc_name,
            "st_name": st_name,
            "norm_state": norm_st,
            "norm_pc": norm_pc,
            "centroid_lon": round(centroid.x, 6),
            "centroid_lat": round(centroid.y, 6),
            "bbox": [round(b, 6) for b in bounds],
            "coordinate_type": "CONSTITUENCY_CENTROID",
            "geo_source": "DataMeet ECI Delimitation 2019"
        }

        # Store in feature
        feature["properties"] = props_enriched
        processed_pc_features.append(feature)

        geo_lookup[(norm_st, norm_pc)] = props_enriched

        if norm_st not in state_polygons:
            state_polygons[norm_st] = []
            state_meta[norm_st] = {"st_name": st_name}
        state_polygons[norm_st].append(geom)

    # Save enriched PC GeoJSON
    with open(PC_GEOJSON_PATH, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": processed_pc_features}, f)
    print(f"Saved enriched PC GeoJSON with centroids to {PC_GEOJSON_PATH}")

    # 2. Dissolve constituencies to create State boundaries
    print("Dissolving constituencies to produce State boundaries...")
    state_features = []
    for norm_st, geoms in state_polygons.items():
        valid_geoms = []
        for g in geoms:
            if not g.is_valid:
                g = g.buffer(0)
            valid_geoms.append(g)
        try:
            state_union = unary_union(valid_geoms)
        except Exception as e:
            from shapely.validation import make_valid
            cleaned = [make_valid(g) for g in valid_geoms]
            state_union = unary_union(cleaned)

        st_centroid = state_union.centroid
        st_bounds = state_union.bounds
        st_name = state_meta[norm_st]["st_name"]

        state_feat = {
            "type": "Feature",
            "properties": {
                "st_name": st_name,
                "norm_state": norm_st,
                "centroid_lon": round(st_centroid.x, 6),
                "centroid_lat": round(st_centroid.y, 6),
                "bbox": [round(b, 6) for b in st_bounds],
                "geo_source": "DataMeet ECI 2019 Derived Dissolved State Boundary"
            },
            "geometry": mapping(state_union)
        }
        state_features.append(state_feat)

    with open(STATE_GEOJSON_PATH, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": state_features}, f)
    print(f"Saved {len(state_features)} state boundaries to {STATE_GEOJSON_PATH}")

    # 3. Match MPLADS Dataset Records
    print("Matching MPLADS dataset against official boundaries...")
    df = pd.read_csv(DATASET_PATH)
    total_projects = len(df)

    # Unique entities in dataset
    entities = df[["state", "constituency"]].drop_duplicates().copy()
    entities["norm_state"] = entities["state"].apply(norm_state)
    entities["clean_pc"] = entities["constituency"].apply(clean_str)

    quality_rows = []
    matched_entity_map = {} # (state, constituency) -> geo_props

    for _, row in entities.iterrows():
        raw_state = str(row["state"])
        raw_pc = str(row["constituency"])
        st_norm = row["norm_state"]
        pc_clean = row["clean_pc"]

        # Check direct match or alias
        target_pc_clean = pc_clean
        if (st_norm, pc_clean) in PC_ALIASES:
            target_pc_clean = clean_str(PC_ALIASES[(st_norm, pc_clean)])

        matched_geo = geo_lookup.get((st_norm, target_pc_clean))

        if matched_geo:
            matched_entity_map[(raw_state, raw_pc)] = matched_geo
            quality_rows.append({
                "geographic_entity": f"{raw_pc}, {raw_state}",
                "state": raw_state,
                "constituency": raw_pc,
                "matched_pc_id": matched_geo["pc_id"],
                "matched_pc_name": matched_geo["pc_name"],
                "mapping_status": "MATCHED",
                "coordinate_type": "CONSTITUENCY_CENTROID",
                "geo_source": "DataMeet ECI Delimitation 2019",
                "validation_status": "VALID",
                "reason": "Normalized exact/alias key match"
            })
        else:
            quality_rows.append({
                "geographic_entity": f"{raw_pc}, {raw_state}",
                "state": raw_state,
                "constituency": raw_pc,
                "matched_pc_id": None,
                "matched_pc_name": None,
                "mapping_status": "UNMATCHED",
                "coordinate_type": "NONE",
                "geo_source": "NONE",
                "validation_status": "UNRESOLVED_GEOGRAPHY",
                "reason": f"No official boundary found for '{raw_pc}' in state '{raw_state}'. Will not place randomly."
            })

    quality_df = pd.DataFrame(quality_rows)
    quality_df.to_csv(QUALITY_REPORT_PATH, index=False)
    print(f"Exported Quality Report to {QUALITY_REPORT_PATH}")

    # Calculate Project-level stats
    matched_count = 0
    unmatched_count = 0
    df_mapped_rows = []

    for _, row in df.iterrows():
        key = (str(row["state"]), str(row["constituency"]))
        geo = matched_entity_map.get(key)
        if geo:
            matched_count += 1
            df_mapped_rows.append({
                "work_code": row["work_code"],
                "pc_id": geo["pc_id"],
                "pc_name": geo["pc_name"],
                "geo_lat": geo["centroid_lat"],
                "geo_lon": geo["centroid_lon"],
                "coordinate_type": "CONSTITUENCY_CENTROID",
                "geo_source": "DataMeet ECI Delimitation 2019",
                "mapping_status": "MATCHED"
            })
        else:
            unmatched_count += 1
            df_mapped_rows.append({
                "work_code": row["work_code"],
                "pc_id": None,
                "pc_name": None,
                "geo_lat": None,
                "geo_lon": None,
                "coordinate_type": "NONE",
                "geo_source": "NONE",
                "mapping_status": "UNMATCHED"
            })

    print(f"Project Matching Summary: {matched_count}/{total_projects} ({matched_count/total_projects*100:.2f}%) matched.")
    print(f"Unmatched project records: {unmatched_count} (Safely quarantined with coordinate_type=NONE).")

    # Update SQLite database with geo metadata table and clean project columns
    print("Updating SQLite database with verified geospatial metadata...")
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Project Geo Mapping table
    pd.DataFrame(df_mapped_rows).to_sql("project_geography", conn, if_exists="replace", index=False)
    
    # 2. Constituencies master table
    constituencies_master = []
    for f in processed_pc_features:
        p = f["properties"]
        constituencies_master.append({
            "pc_id": p["pc_id"],
            "pc_no": p["pc_no"],
            "pc_name": p["pc_name"],
            "st_name": p["st_name"],
            "norm_state": p["norm_state"],
            "norm_pc": p["norm_pc"],
            "centroid_lon": p["centroid_lon"],
            "centroid_lat": p["centroid_lat"],
            "bbox": json.dumps(p["bbox"]),
            "geo_source": p["geo_source"]
        })
    pd.DataFrame(constituencies_master).to_sql("constituencies_master", conn, if_exists="replace", index=False)

    # 3. Create index for high performance queries
    cur = conn.cursor()
    cur.execute("CREATE INDEX IF NOT EXISTS idx_proj_geo_work_code ON project_geography(work_code)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_proj_geo_pc_id ON project_geography(pc_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_constituencies_master_pc_id ON constituencies_master(pc_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_constituencies_master_st_name ON constituencies_master(st_name)")
    conn.commit()
    conn.close()
    print("Geospatial database setup completed successfully.")

if __name__ == "__main__":
    run_preprocessing()
