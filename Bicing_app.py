import streamlit as st
import random
import folium # For maps
from streamlit_folium import st_folium # To display folium maps in Streamlit

# --- Configuration ---
NUM_STATIONS = 8
LOW_BIKE_THRESHOLD_PERCENT = 0.25 # Up to 25% bikes -> orange
EMPTY_STATION_THRESHOLD_PERCENT = 0.10 # Stations with <= 10% bikes are "critically empty"

MIN_CAPACITY = 16
MAX_CAPACITY = 24
MAX_WAITING_USERS = 5
MAP_HEIGHT = 500

STATION_INFO = {
    "Plaza Catalunya": (41.3870, 2.1700), "Passeig de Gracia": (41.3925, 2.1650),
    "Sagrada Familia": (41.4036, 2.1744), "Barceloneta Beach": (41.3780, 2.1890),
    "Camp Nou": (41.3809, 2.1228), "Gracia - Vila": (41.3984, 2.1570),
    "El Born CCM": (41.3849, 2.1818), "Sants Estacio": (41.3790, 2.1400),
    "Parc Guell": (41.4145, 2.1520), "Diagonal Mar Park": (41.4060, 2.2170),
    "Poblenou Park": (41.4000, 2.2000), "Les Corts": (41.3830, 2.1300)
}
AVAILABLE_STATION_NAMES = list(STATION_INFO.keys())
BARCELONA_CENTER_COORD = (41.3900, 2.1650)
PRIMARY_RED_COLOR = "#D32F2F"
SECONDARY_RED_COLOR = "#FF4B4B"
LIGHT_RED_COLOR_HEX = "#FFCDD2"
INCENTIVE_GREEN_COLOR = "#4CAF50"

# --- Helper Functions ---

def get_map_marker_details(station):
    bikes = station['available_bikes']
    docks = station['free_docks']
    capacity = station['total_capacity']
    waiting_rent = station['waiting_to_rent']
    waiting_return = station['waiting_to_return']

    icon_name = 'bicycle'
    icon_prefix = 'fa'
    color = 'green' 

    if bikes == 0:
        color = 'red'
        if waiting_rent > 0:
            color = 'darkred'
            icon_name = 'user-clock'
    elif bikes <= capacity * LOW_BIKE_THRESHOLD_PERCENT:
        color = 'orange'
    else: 
        color = 'green'

    if docks == 0 and waiting_return > 0:
        icon_name = 'user-clock'

    return color, icon_name, icon_prefix


def initialize_stations():
    if 'stations' not in st.session_state:
        st.session_state.stations = []
        
        if NUM_STATIONS <= len(AVAILABLE_STATION_NAMES):
            selected_names_keys = random.sample(AVAILABLE_STATION_NAMES, k=NUM_STATIONS)
        else:
            selected_names_keys = random.sample(AVAILABLE_STATION_NAMES, k=len(AVAILABLE_STATION_NAMES))
            selected_names_keys += random.choices(AVAILABLE_STATION_NAMES, k=NUM_STATIONS - len(AVAILABLE_STATION_NAMES))

        special_no_bikes_id = 0 if NUM_STATIONS >= 1 else -1
        special_full_station_id = 1 if NUM_STATIONS >= 2 else -1

        if special_no_bikes_id != -1 and special_no_bikes_id == special_full_station_id:
            special_full_station_id = -1

        for i in range(NUM_STATIONS):
            name_key = selected_names_keys[i]
            lat, lon = STATION_INFO[name_key]
            total_capacity = random.choice([c for c in range(MIN_CAPACITY, MAX_CAPACITY + 1) if c % 2 == 0])
            
            station_data = {
                "id": i, "name": name_key,
                "lat": lat + random.uniform(-0.0005, 0.0005), "lon": lon + random.uniform(-0.0005, 0.0005),
                "total_capacity": total_capacity, "available_bikes": 0, "free_docks": 0,
                "waiting_to_rent": 0, "waiting_to_return": 0
            }

            if i == special_no_bikes_id: # Critically Empty Station
                station_data.update({
                    "available_bikes": 0, "free_docks": total_capacity,
                    "waiting_to_rent": random.randint(1, MAX_WAITING_USERS), "waiting_to_return": 0
                })
            elif i == special_full_station_id: # Critically Full Station
                station_data.update({
                    "available_bikes": total_capacity, "free_docks": 0,
                    "waiting_to_rent": 0, "waiting_to_return": random.randint(1, MAX_WAITING_USERS)
                })
            else: # Normal Stations (bike <= docks rule)
                max_bikes_allowed = total_capacity // 2
                # Ensure some stations can become "critically empty" for the incentive
                if random.random() < 0.2: # 20% chance to be very empty
                     station_data["available_bikes"] = random.randint(0, int(total_capacity * EMPTY_STATION_THRESHOLD_PERCENT))
                else:
                    station_data["available_bikes"] = random.randint(0, max_bikes_allowed)
                
                station_data["free_docks"] = total_capacity - station_data["available_bikes"]
                station_data["waiting_to_rent"] = 0 # Will be set to 0 if bikes > 0 later
                station_data["waiting_to_return"] = 0 # Will be set to 0 if docks > 0 later
            st.session_state.stations.append(station_data)

        for station in st.session_state.stations:
            if station["id"] == special_no_bikes_id or station["id"] == special_full_station_id:
                # For special stations, waiting queues are part of their defined problem state
                if station["id"] == special_no_bikes_id and station["available_bikes"] == 0 and station["waiting_to_rent"] == 0:
                    station["waiting_to_rent"] = random.randint(1, MAX_WAITING_USERS) # Ensure waiting if no bikes
                elif station["id"] == special_full_station_id and station["free_docks"] == 0 and station["waiting_to_return"] == 0:
                    station["waiting_to_return"] = random.randint(1, MAX_WAITING_USERS) # Ensure waiting if no docks
                continue
            
            # For normal stations, clear waiting queues if resources are available
            if station["available_bikes"] > 0: station["waiting_to_rent"] = 0
            if station["free_docks"] > 0: station["waiting_to_return"] = 0
            
            # Enforce bike <= dock rule for normal stations, if somehow violated
            if station["available_bikes"] > station["free_docks"]:
                station["available_bikes"] = station["total_capacity"] // 2
                station["free_docks"] = station["total_capacity"] - station["available_bikes"]

def find_alternative_station(current_station_id, stations, need_bikes=False, need_docks=False):
    best_alternative = None; max_score = -float('inf')
    for station in stations:
        if station["id"] == current_station_id: continue
        if need_bikes and station["available_bikes"] > 0:
            penalty = 100 if station["id"] == 1 and station["free_docks"] == 0 else 0
            score = station["available_bikes"] - (station["waiting_to_rent"] * 0.5) - penalty
            if score > max_score: max_score = score; best_alternative = station
        elif need_docks and station["free_docks"] > 0:
            penalty = 100 if station["id"] == 0 and station["available_bikes"] == 0 else 0
            score = station["free_docks"] - (station["waiting_to_return"] * 0.5) - penalty
            if score > max_score: max_score = score; best_alternative = station
    return best_alternative

def create_station_map(stations_data):
    m = folium.Map(location=BARCELONA_CENTER_COORD, zoom_start=13, tiles="CartoDB positron")
    for station in stations_data:
        popup_html = f"""<b>{station['name']}</b><br>--------------------------<br>
                        Bikes: {station['available_bikes']}<br>
                        Docks: {station['free_docks']}<br>
                        Capacity: {station['total_capacity']}<br>
                        Wait Rent: {station['waiting_to_rent']}<br>Wait Return: {station['waiting_to_return']}"""
        color, icon_name, icon_prefix = get_map_marker_details(station)
        folium.Marker(
            location=[station['lat'], station['lon']],
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{station['name']}: {station['available_bikes']} bikes, {station['free_docks']} docks",
            icon=folium.Icon(color=color, icon=icon_name, prefix=icon_prefix)
        ).add_to(m)
    return m

# --- Main App ---
st.set_page_config(layout="wide")

st.markdown(f"""
    <style>
        .main .block-container {{ background-color: white !important; color: {PRIMARY_RED_COLOR} !important; }}
        body {{ background-color: white !important; }}
        h1, h2, h3, h4, h5, h6 {{ color: {PRIMARY_RED_COLOR} !important; }}
        [data-testid="stSidebar"] {{ background-color: #f8f9fa !important; }}
        [data-testid="stSidebar"] * {{ color: {PRIMARY_RED_COLOR} !important; }}
        [data-testid="stSidebar"] .stButton>button {{
            background-color: {PRIMARY_RED_COLOR} !important; color: white !important;
            border: 1px solid {PRIMARY_RED_COLOR} !important;
        }}
        div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] > div:has(div[data-testid="stFoliumMap"]) + div {{
            margin-top: -30px !important;
        }}
        .stButton>button {{
            background-color: white !important; color: {SECONDARY_RED_COLOR} !important;
            border: 2px solid {SECONDARY_RED_COLOR} !important; border-radius: 5px; font-weight: bold;
        }}
        .stButton>button:hover {{ background-color: {SECONDARY_RED_COLOR} !important; color: white !important; }}
        .stButton>button:disabled {{
            background-color: #f8f9fa !important; color: #adb5bd !important;
            border-color: #dee2e6 !important;
        }}
        div[data-testid="stMetric"] {{
            background-color: white; border: 1px solid {LIGHT_RED_COLOR_HEX};
            padding: 0.75rem; border-radius: 0.25rem; text-align: center;
        }}
        div[data-testid="stMetric"] label {{ color: {PRIMARY_RED_COLOR} !important; font-size: 0.9em; }}
        div[data-testid="stMetricValue"] {{ font-size: 1.7em; font-weight: bold; color: {PRIMARY_RED_COLOR} !important; }}
        div[data-testid="stAlert"] {{
            border-radius: 5px; border-left: 5px solid {PRIMARY_RED_COLOR} !important;
        }}
        div[data-testid="stAlert"] p, div[data-testid="stAlert"] li {{ color: {PRIMARY_RED_COLOR} !important; }}
        div[data-testid="stInfo"] {{ background-color: #ffebee !important; }}
        div[data-testid="stError"] {{ background-color: #ffcdd2 !important; }}
        div[data-testid="stWarning"] {{ background-color: #FFEBEE !important; }}
        .incentive-electric-bike {{
            background-color: {INCENTIVE_GREEN_COLOR} !important;
            color: white !important; padding: 10px; border-radius: 5px;
            text-align: center; font-weight: bold; margin-top: 10px;
            border: 2px solid {INCENTIVE_GREEN_COLOR};
        }}
        .incentive-electric-bike p {{ color: white !important; margin-bottom: 0; }}
        .custom-card-content {{ /* Added to wrap main card content */
            flex-grow: 1; /* Allows this part to take up space */
        }}
        .custom-card-incentive-area {{ /* For the incentive or placeholder */
            min-height: 60px; /* Ensure space for incentive visibility */
            display: flex;
            align-items: center; /* Center placeholder text if any */
            justify-content: center;
        }}
    </style>
    """, unsafe_allow_html=True)

st.title("BIKING BARCELONA - Crowd Simulation")
initialize_stations()

st.sidebar.header("SIMULATION CONTROLS")
if st.sidebar.button("Simulate Time Passing (Refresh Data)"):
    if 'stations' in st.session_state: del st.session_state.stations
    initialize_stations(); st.rerun()

st.sidebar.markdown("### Map Legend (Bike Availability)")
st.sidebar.markdown(f"""
- <font color='darkred'>Dark Red (User Clock)</font>: No bikes, users waiting.
- <font color='red'>Red (Bicycle)</font>: No bikes.
- <font color='orange'>Orange (Bicycle)</font>: Few bikes (≤ {LOW_BIKE_THRESHOLD_PERCENT*100:.0f}% capacity).
- <font color='green'>Green (User Clock)</font>: Many bikes, BUT station full & users waiting to return (ID 1 Demo).
- <font color='green'>Green (Bicycle)</font>: Good bike availability.
""", unsafe_allow_html=True)

st.header("Live Station Map")
station_map_object = create_station_map(st.session_state.stations)
MAP_COMPONENT_KEY = "bicing_folium_map"
st_folium(station_map_object, width=None, height=MAP_HEIGHT, key=MAP_COMPONENT_KEY)

st.header("Station Details & Actions")
cols_per_row = 4
cols = st.columns(cols_per_row)
# Card height is now managed by flexbox mostly, but an explicit height on the outer div can help.
# Let's remove fixed height on the outer div and let content + min-height of incentive area dictate it.

for i, station in enumerate(st.session_state.stations):
    col = cols[i % cols_per_row]
    
    # Using st.markdown for the card structure with flexbox
    st.markdown(f"""
    <div style="border: 2px solid {LIGHT_RED_COLOR_HEX}; border-radius: 5px; padding: 15px; margin-bottom:10px; display: flex; flex-direction: column; min-height: 500px;"> 
    <div class="custom-card-content"> 
    """, unsafe_allow_html=True) # min-height added to ensure cards have some initial size
    
    st.subheader(f"{station['name']}")
    metric_col1, metric_col2 = st.columns(2)
    with metric_col1:
        st.metric(label="🚲 Bikes", value=station['available_bikes'])
        st.metric(label="🧍 Rent Queue", value=station['waiting_to_rent'])
    with metric_col2:
        st.metric(label="🅿️ Docks", value=station['free_docks'])
        st.metric(label="🧍 Return Queue", value=station['waiting_to_return'])
    st.caption(f"Capacity: {station['total_capacity']}")

    btn_col1, btn_col2 = st.columns(2)
    rent_disabled = station['available_bikes'] > 0
    return_disabled = station['free_docks'] > 0

    if btn_col1.button("Wait to RENT", key=f"rent_{station['id']}", use_container_width=True, disabled=rent_disabled):
        st.session_state.stations[i]['waiting_to_rent'] = min(MAX_WAITING_USERS + 5, station['waiting_to_rent'] + 1)
        st.rerun()
    if btn_col2.button("Wait to RETURN", key=f"return_{station['id']}", use_container_width=True, disabled=return_disabled):
        st.session_state.stations[i]['waiting_to_return'] = min(MAX_WAITING_USERS + 5, station['waiting_to_return'] + 1)
        st.rerun()

    messages = [] # For st.error and st.info messages
    
    # Determine if this station is eligible for the "critically empty" electric bike incentive
    is_critically_empty_for_incentive = (
        station['available_bikes'] <= station['total_capacity'] * EMPTY_STATION_THRESHOLD_PERCENT and
        station['id'] != 0 and # Not the forced "no bikes" demo station
        station['id'] != 1    # Not the forced "full" demo station
    )

    # --- Standard Problem Messages & Other Incentives ---
    is_problem_no_bikes = station["id"] == 0 and station["available_bikes"] == 0 and station["waiting_to_rent"] > 0
    is_problem_full_station = station["id"] == 1 and station["free_docks"] == 0 and station["waiting_to_return"] > 0

    if is_problem_no_bikes:
        messages.append(("error", f"⛔ No bikes! {station['waiting_to_rent']} user(s) waiting."))
        alt = find_alternative_station(station['id'], st.session_state.stations, need_bikes=True)
        if alt: messages.append(("info", f"💡 Try **{alt['name']}**: {alt['available_bikes']} bikes."))
        else: messages.append(("info", "⚠️ No other stations with bikes found."))
    elif station['available_bikes'] == 0:
         messages.append(("error", "⛔ No bikes available!"))
         if station['waiting_to_rent'] > 0: messages.append(("info", f"👥 {station['waiting_to_rent']} user(s) now waiting."))
         alt = find_alternative_station(station['id'], st.session_state.stations, need_bikes=True)
         if alt: messages.append(("info", f"💡 Try **{alt['name']}**: {alt['available_bikes']} bikes."))

    if is_problem_full_station:
        messages.append(("error", f"🅿️ Station full! {station['waiting_to_return']} user(s) waiting."))
        alt = find_alternative_station(station['id'], st.session_state.stations, need_docks=True)
        if alt:
            messages.append(("info", f"💡 Try returning at **{alt['name']}**: {alt['free_docks']} docks."))
            messages.append(("info", f"💰 **Incentive:** Return at **{alt['name']}** & earn **1 Bicing Credit!**"))
        else: messages.append(("info", "⚠️ No other stations with free docks found."))
    elif station['free_docks'] == 0:
        messages.append(("error", "🅿️ Station full! No free docks."))
        if station['waiting_to_return'] > 0: messages.append(("info", f"👥 {station['waiting_to_return']} user(s) now waiting."))
        alt = find_alternative_station(station['id'], st.session_state.stations, need_docks=True)
        if alt:
            messages.append(("info", f"💡 Try returning at **{alt['name']}**: {alt['free_docks']} docks."))
            messages.append(("info", f"💰 **Incentive:** Return at **{alt['name']}** & earn **1 Bicing Credit!**"))
    
    # Display collected st.error/st.info messages
    for msg_type, msg_text in messages:
        if msg_type == "error": st.error(msg_text)
        elif msg_type == "info": st.info(msg_text)

    # General Rebalancing "Bonus" incentives (if no specific "Bicing Credit" and not getting electric bike one)
    already_has_specific_incentive = any("Bicing Credit!" in msg_text for _, msg_text in messages)
    if not already_has_specific_incentive and not is_critically_empty_for_incentive:
        if station['available_bikes'] <= station['total_capacity'] * 0.25 and station['free_docks'] > 0 and station['id'] !=0 :
             st.info(f"✨ **Help Rebalance!** Return bike at **{station['name']}** & earn a **Bonus!**") # Directly display
        elif station['available_bikes'] >= station['total_capacity'] * 0.40 and station['available_bikes'] <= station['total_capacity'] * 0.50 and station['id'] !=1:
             st.info(f"✨ **Help Rebalance!** Take bike from **{station['name']}** & earn a **Bonus!**") # Directly display
    
    st.markdown("</div> <!-- End custom-card-content -->", unsafe_allow_html=True)

    # --- Electric Bike Incentive Area (at the bottom of the card) ---
    st.markdown("<div class='custom-card-incentive-area'>", unsafe_allow_html=True)
    if is_critically_empty_for_incentive:
        st.markdown(f"""
        <div class="incentive-electric-bike">
            <p>🌟 FREE E-RIDE! 🌟<br>Bring a bike to <b>{station['name']}</b> and get your next electric ride FREE!</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # st.markdown("<p> </p>", unsafe_allow_html=True) # Placeholder to maintain space
        pass # Or simply nothing if no incentive
    st.markdown("</div> <!-- End custom-card-incentive-area -->", unsafe_allow_html=True)
    
    st.markdown("</div> <!-- End Outer Card Div -->", unsafe_allow_html=True)