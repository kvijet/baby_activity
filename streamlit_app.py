import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import pandas as pd

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
    actions = ['Slept', 'Woke Up','Water', 'Fed', 'Solid Food', 'Potty', 'Diaper Change']
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
    
    # Add refresh button
    col_refresh, col_save = st.columns([1, 4])
    with col_refresh:
        refresh_clicked = st.button("🔄 Refresh", key="refresh_button")
    
    # Load data function
    def load_recent_data():
        data = sheet.get_all_values()
        if data:
            headers = data[0]
            records = data[1:]

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
            df_recent = df_recent.sort_values("datetime", ascending=False).reset_index(drop=True)
            
            return df, df_recent, ist, two_days_ago
        return None, None, None, None
    
    # Load data
    df, df_recent, ist, two_days_ago = load_recent_data()
    
    # Create a placeholder for the data editor
    data_placeholder = st.empty()
    
    if df is not None and df_recent is not None:
        # Keep datetime for mapping, but don't show it in editor
        df_recent_display = df_recent.drop(columns=["datetime"])

        with data_placeholder.container():
            edited_df = st.data_editor(df_recent_display, num_rows="dynamic", key="activity_editor", hide_index=True)

        with col_save:
            save_clicked = st.button("💾 Save Changes", key="save_button")
        
        if save_clicked:
            # Recreate datetime column in edited_df from Date and Time columns
            edited_df["datetime"] = pd.to_datetime(edited_df["Date"] + " " + edited_df["Time"])
            edited_df["datetime"] = edited_df["datetime"].dt.tz_localize(ist, ambiguous='NaT', nonexistent='shift_forward')
            
            # Get original data with datetime
            original_df_with_datetime = df[df["datetime"] >= two_days_ago].sort_values("datetime", ascending=False).copy()
            
            # Check if there are changes
            has_changes = False
            
            if len(edited_df) != len(original_df_with_datetime):
                has_changes = True
            else:
                # Compare without datetime column
                original_compare = original_df_with_datetime.drop(columns=["datetime"]).reset_index(drop=True)
                edited_compare = edited_df.drop(columns=["datetime"]).reset_index(drop=True)
                try:
                    changes = edited_compare.compare(original_compare)
                    has_changes = not changes.empty
                except:
                    has_changes = True
            
            if has_changes:
                # Create a mapping of datetime to sheet row for the full dataset
                datetime_to_sheet_row = {}
                for idx, row in df.iterrows():
                    datetime_to_sheet_row[row["datetime"]] = idx + 2  # +2 for header and 1-indexing
                
                # Get column names from the dataframe (excluding datetime)
                data_columns = [col for col in edited_df.columns if col != "datetime"]
                
                # Find rows to delete (in original but not in edited)
                original_datetimes = set(original_df_with_datetime["datetime"])
                edited_datetimes = set(edited_df["datetime"])
                deleted_datetimes = original_datetimes - edited_datetimes
                
                # Delete rows (in reverse order to avoid row number shifting)
                rows_to_delete = sorted([datetime_to_sheet_row[dt] for dt in deleted_datetimes], reverse=True)
                for sheet_row in rows_to_delete:
                    sheet.delete_rows(sheet_row)
                
                # Update the datetime_to_sheet_row mapping after deletions
                # Reload the sheet to get accurate row numbers
                data = sheet.get_all_values()
                df_refreshed = pd.DataFrame(data[1:], columns=data[0])
                df_refreshed["datetime"] = pd.to_datetime(df_refreshed["Date"] + " " + df_refreshed["Time"])
                df_refreshed["datetime"] = df_refreshed["datetime"].dt.tz_localize(ist, ambiguous='NaT', nonexistent='shift_forward')
                
                datetime_to_sheet_row = {}
                for idx, row in df_refreshed.iterrows():
                    datetime_to_sheet_row[row["datetime"]] = idx + 2
                
                # Update or add rows using datetime matching
                for idx, edited_row in edited_df.iterrows():
                    edited_datetime = edited_row["datetime"]
                    
                    # Check if this datetime exists in the sheet
                    if edited_datetime in datetime_to_sheet_row:
                        # Update existing row
                        sheet_row = datetime_to_sheet_row[edited_datetime]
                        row_values = [edited_row[col] for col in data_columns]
                        end_col = chr(65 + len(row_values) - 1)
                        sheet.update(f'A{sheet_row}:{end_col}{sheet_row}', [row_values])
                    else:
                        # New row added, append to the end
                        row_values = [edited_row[col] for col in data_columns]
                        sheet.append_row(row_values)
                
                st.success("Changes saved to Google Sheet!")
                # Trigger refresh logic by setting a session state variable
                st.session_state["refresh_button"] = True
            else:
                st.info("No changes to save.")
    else:
        st.info("No data found.")