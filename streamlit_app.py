
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

st.set_page_config(page_title="Suddu Tracker")
st.title("Suddu Tracker")

# Use your provided authentication variables
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds_dict = st.secrets["service_account"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("baby_tracking").sheet1

# Get IST date and time
def get_ist_datetime():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')
    return date_str, time_str

# Layout: two containers
container1, container2 = st.columns([1, 2])

with container1:
    st.header("Add Activity")
    actions = ['Slept', 'Woke Up', 'Fed', 'Solid Food', 'Potty', 'Diaper Change']
    for action in actions:
        if st.button(action):
            date, time = get_ist_datetime()
            notes_key = f"notes_{action.replace(' ', '_')}"
            notes = st.text_input(f"Notes for {action}", key=notes_key)
            # Only add row when notes is entered or left blank and button pressed; use session state to reduce multiple entries
            if 'submitted_action' not in st.session_state or st.session_state['submitted_action'] != action:
                new_row = [date, time, action, notes]
                sheet.append_row(new_row)
                st.session_state['submitted_action'] = action
                st.success(f"Recorded: {action} at {date} {time}")

with container2:
    st.header("Recent Activity")
    data = sheet.get_all_values()
    if data:
        headers = data[0]
        records = data[1:]
        import pandas as pd
        
        df = pd.DataFrame(records, columns=headers)
        
        # Combine Date and Time to a single datetime column
        df["datetime"] = pd.to_datetime(df["Date"] + " " + df["Time"])
        
        # Filter for last 2 days in IST
        ist = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(ist)
        two_days_ago = now_ist - pd.Timedelta(days=2)
        df["datetime"] = df["datetime"].dt.tz_localize(ist, ambiguous='NaT', nonexistent='shift_forward')
        df_recent = df[df["datetime"] >= two_days_ago]
        
        # Sort descending by datetime
        df_recent = df_recent.sort_values("datetime", ascending=False)
        
        # Drop 'datetime' column if you don't want to show it
        

        edited_df = st.data_editor(df_recent, num_rows="dynamic", key="activity_editor", hide_index=True)
        
        if st.button("Save Changes"):
            # Comparison logic as before, but only for filtered df 
            original_df = df[df["datetime"] >= two_days_ago].sort_values("datetime", ascending=False).drop(columns=["datetime"])
            changes = edited_df.compare(original_df)
            if not changes.empty:
                for idx in changes.index.get_level_values(0).unique():
                    sheet_idx = original_df.index[idx] + 2 # mapping filtered idx to sheet row (header + 1-indexed)
                    sheet.update(f'A{sheet_idx}:{chr(65+len(headers)-1)}{sheet_idx}', [list(edited_df.loc[idx])])
                st.success("Changes saved to Google Sheet!")
            else:
                st.info("No changes to save.")
    else:
        st.info("No data found.")
        
st.header("Analytics")

col1, col2 = st.columns(2)
with col1:
    day_start_time = st.time_input(
        "Select Baby's day start time",
        value=datetime.strptime("09:00", "%H:%M").time()
    )
with col2:
    num_days = st.number_input(
        "Select number of days for analytics",
        min_value=1,
        max_value=30,
        value=3,  # Default to 3 days
        step=1
    )
# Calculate analytics cutoff datetime
ist = pytz.timezone('Asia/Kolkata')
now_ist = datetime.now(ist)

# Combine today's date with the selected day_start_time
cutoff_datetime = datetime.combine(now_ist.date(), day_start_time)
cutoff_datetime = ist.localize(cutoff_datetime)

# Go back num_days from the cutoff
analytics_start_datetime = cutoff_datetime - pd.Timedelta(days=num_days)

# Display for development
st.subheader("Analytics Date Range (Development View)")
st.write(f"Current IST Time: {now_ist.strftime('%Y-%m-%d %H:%M:%S')}")
st.write(f"Day Start Time Selected: {day_start_time.strftime('%H:%M')}")
st.write(f"Number of Days: {num_days}")
st.write(f"Analytics Start DateTime: {analytics_start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
st.write(f"Analytics End DateTime: {cutoff_datetime.strftime('%Y-%m-%d %H:%M:%S')}")

# Filter data for analytics
if data:
    df_analytics = df.copy()
    df_analytics = df_analytics[
        (df_analytics["datetime"] >= analytics_start_datetime) & 
        (df_analytics["datetime"] <= cutoff_datetime)
    ]
    
    st.subheader("Filtered Data for Analytics")
    st.write(f"Total records in range: {len(df_analytics)}")
    st.dataframe(df_analytics)
    
    # Split data into daily groups
    st.subheader("Daily Groups (Development View)")
    
    daily_groups = {}
    for day_offset in range(num_days):
        day_start = analytics_start_datetime + pd.Timedelta(days=day_offset)
        day_end = analytics_start_datetime + pd.Timedelta(days=day_offset + 1)
        
        day_data = df_analytics[
            (df_analytics["datetime"] >= day_start) & 
            (df_analytics["datetime"] < day_end)
        ].copy()
        
        # Check if "Woke Up" appears before "Slept"
        if not day_data.empty:
            first_slept = day_data[day_data["Activity"] == "Slept"]["datetime"].min() if "Slept" in day_data["Activity"].values else None
            first_woke_up = day_data[day_data["Activity"] == "Woke Up"]["datetime"].min() if "Woke Up" in day_data["Activity"].values else None
            
            # Add "Slept" at start of day if "Woke Up" comes before first "Slept"
            if first_woke_up is not None and (first_slept is None or first_woke_up < first_slept):
                new_row = pd.DataFrame({
                    "Date": [day_start.strftime('%Y-%m-%d')],
                    "Time": [day_start.strftime('%H:%M:%S')],
                    "Activity": ["Slept"],
                    "Notes": ["Auto-added: Day started with wake up"],
                    "datetime": [day_start]
                })
                day_data = pd.concat([new_row, day_data]).sort_values("datetime")
            
            # For days excluding current day, check if "Slept" is not followed by "Woke Up"
            is_current_day = (day_offset == num_days - 1)
            if not is_current_day:
                last_slept = day_data[day_data["Activity"] == "Slept"]["datetime"].max() if "Slept" in day_data["Activity"].values else None
                if last_slept is not None:
                    woke_up_after_slept = day_data[(day_data["Activity"] == "Woke Up") & (day_data["datetime"] > last_slept)]
                    if woke_up_after_slept.empty:
                        new_row = pd.DataFrame({
                            "Date": [day_end.strftime('%Y-%m-%d')],
                            "Time": [day_end.strftime('%H:%M:%S')],
                            "Activity": ["Woke Up"],
                            "Notes": ["Auto-added: No wake up found after last sleep"],
                            "datetime": [day_end]
                        })
                        day_data = pd.concat([day_data, new_row]).sort_values("datetime")
        
        daily_groups[f"Day {day_offset + 1} ({day_start.strftime('%Y-%m-%d')})"] = day_data
        
        st.write(f"**Day {day_offset + 1}: {day_start.strftime('%Y-%m-%d %H:%M')} to {day_end.strftime('%Y-%m-%d %H:%M')}**")
        st.write(f"Records: {len(day_data)}")
        st.dataframe(day_data)