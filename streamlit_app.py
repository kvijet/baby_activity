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
        df_recent = df_recent.drop(columns=["datetime"])

        edited_df = st.data_editor(df_recent, num_rows="dynamic", key="activity_editor", hide_index=True)

        if st.button("Save Changes"):
            original_df = df[df["datetime"] >= two_days_ago].sort_values("datetime", ascending=False).drop(columns=["datetime"])
            
            # Reset indexes for comparison
            edited_df_reset = edited_df.reset_index(drop=True)
            original_df_reset = original_df.reset_index(drop=True)
            
            # Check if there are changes (different lengths or different content)
            has_changes = False
            
            if len(edited_df_reset) != len(original_df_reset):
                has_changes = True
            else:
                # Only compare if same length
                try:
                    changes = edited_df_reset.compare(original_df_reset)
                    has_changes = not changes.empty
                except:
                    has_changes = True
            
            if has_changes:
                # Clear and rewrite all rows in the filtered range
                # Get the starting row number in the sheet
                start_row = 2  # Assuming row 1 is headers
                
                # Write all edited rows back to sheet
                for idx, row in edited_df_reset.iterrows():
                    row_values = list(row)
                    sheet_row = start_row + idx
                    sheet.update(f'A{sheet_row}:{chr(65+len(row_values)-1)}{sheet_row}', [row_values])
                
                st.success("Changes saved to Google Sheet!")

                # Refresh table with latest records from Google Sheets
                data = sheet.get_all_values()
                if data:
                    headers = data[0]
                    records = data[1:]
                    df = pd.DataFrame(records, columns=headers)
                    df["datetime"] = pd.to_datetime(df["Date"] + " " + df["Time"])
                    df["datetime"] = df["datetime"].dt.tz_localize(ist, ambiguous='NaT', nonexistent='shift_forward')
                    df_recent = df[df["datetime"] >= two_days_ago]
                    df_recent = df_recent.sort_values("datetime", ascending=False)
                    df_recent = df_recent.drop(columns=["datetime"])
                    st.dataframe(df_recent, hide_index=True)
            else:
                st.info("No changes to save.")
    else:
        st.info("No data found.")