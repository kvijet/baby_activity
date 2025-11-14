import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

from datetime import time as dtime
st.sidebar.header("Analytics Day Definition")
default_start_time = dtime(9, 0)
day_start_time = st.sidebar.time_input("Baby day start time", value=default_start_time)

def get_baby_day_boundaries(now_ist, day_start_time):
    today_start = now_ist.replace(hour=day_start_time.hour, minute=day_start_time.minute, second=0, microsecond=0)
    if now_ist.time() < day_start_time:
        today_start -= timedelta(days=1)
    yesterday_start = today_start - timedelta(days=1)
    tomorrow_start = today_start + timedelta(days=1)
    return yesterday_start, today_start, tomorrow_start

def day_analytics(df_day):
    actions = {'Fed': 0, 'Solid Food': 0, 'Potty': 0, 'Diaper Change': 0}
    sleep_blocks = []
    df_day = df_day.sort_values("datetime")
    asleep_time = None
    for idx, row in df_day.iterrows():
        action = row["Action"]
        dt = row["datetime"]
        if action in actions:
            actions[action] += 1
        if action == "Slept":
            asleep_time = dt
        elif action == "Woke Up" and asleep_time:
            sleep_start = max(asleep_time, df_day["datetime"].min())
            sleep_end = min(dt, df_day["datetime"].max())
            sleep_blocks.append((asleep_time, dt))
            asleep_time = None
    if asleep_time:
        sleep_blocks.append((asleep_time, df_day["datetime"].max()))
    total_sleep_minutes = sum((min(dt2, df_day["datetime"].max()) - max(dt1, df_day["datetime"].min())).total_seconds() / 60 for dt1, dt2 in sleep_blocks)
    return {
        "Fed count": actions['Fed'],
        "Solid food count": actions['Solid Food'],
        "Potty count": actions['Potty'],
        "Diaper change count": actions['Diaper Change'],
        "Total sleep (hours)": round(total_sleep_minutes / 60, 2)
    }

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
        
        df_recent = df_recent.drop(columns=["datetime"])
        
        if not df.empty:
            now_ist = datetime.now(ist)
            yesterday_start, today_start, tomorrow_start = get_baby_day_boundaries(now_ist, day_start_time)
            df["datetime"] = pd.to_datetime(df["Date"] + " " + df["Time"])
            df["datetime"] = df["datetime"].dt.tz_localize(ist, ambiguous='NaT', nonexistent='shift_forward')
            df_yesterday = df[(df["datetime"] >= yesterday_start) & (df["datetime"] < today_start)].copy()
            df_today = df[(df["datetime"] >= today_start) & (df["datetime"] < tomorrow_start)].copy()
            analytics_yesterday = day_analytics(df_yesterday)
            analytics_today = day_analytics(df_today)
            st.subheader("Baby Activity Analytics (Last Two Days)")
            st.markdown(f"**Yesterday ({yesterday_start.strftime('%Y-%m-%d %H:%M')} - {today_start.strftime('%Y-%m-%d %H:%M')})**")
            for k, v in analytics_yesterday.items():
                st.write(f"{k}: {v}")
            st.markdown(f"**Today ({today_start.strftime('%Y-%m-%d %H:%M')} - {tomorrow_start.strftime('%Y-%m-%d %H:%M')})**")
            for k, v in analytics_today.items():
                st.write(f"{k}: {v}")        
        
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