import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import pandas as pd
import streamlit as st
from pathlib import Path


def load_css(app_dir=None):
    """
    Loads a custom CSS file from the 'assets/style.css' path relative to the current file
    and injects its contents into a Streamlit app using st.markdown. If the CSS file is not found,
    displays a warning and falls back to default Streamlit styling.

    This function enhances the visual appearance of the Streamlit app by applying custom styles.
    """
    if app_dir is None:
        app_dir = Path.cwd()
    else:
        app_dir = Path(app_dir)
    
    css_file = app_dir / "assets" / "style.css"
    if css_file.exists():
        with open(css_file) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    else:
        st.warning(f"Custom CSS file not found at {css_file}. Using default styling.")

def get_ist_datetime():
    """Get current date and time in IST timezone"""
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')
    return date_str, time_str

def load_sheet_data(_sheet):
    """Load all data from Google Sheet"""
    try:
        data = _sheet.get_all_values()
        return data
    except Exception as e:
        st.error(f"Error loading data from Google Sheets: {str(e)}")
        return None

def initialize_google_sheets(creds_dict):
    """Initialize Google Sheets client and return sheet object"""
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("baby_tracking").sheet1
    return sheet

def process_dataframe(data, ist):
    """Process raw sheet data into a pandas DataFrame with datetime column"""
    if not data or len(data) <= 1:
        return None
    
    try:
        headers = data[0]
        records = data[1:]
        
        df_all = pd.DataFrame(records, columns=headers)
        
        # Strip whitespace from column names
        df_all.columns = df_all.columns.str.strip()
        
        # Verify required columns exist
        required_columns = ['Date', 'Time', 'Action']
        missing_columns = [col for col in required_columns if col not in df_all.columns]
        
        if missing_columns:
            st.error(f"Missing required columns in sheet: {', '.join(missing_columns)}")
            st.info(f"Available columns: {', '.join(df_all.columns.tolist())}")
            return None
        
        df_all["datetime"] = pd.to_datetime(df_all["Date"] + " " + df_all["Time"])
        df_all["datetime"] = df_all["datetime"].dt.tz_localize(ist, ambiguous='NaT', nonexistent='shift_forward')
        return df_all
    except Exception as e:
        st.error(f"Error processing data: {str(e)}")
        return None

def load_recent_data(df_all, now_ist):
    """Filter dataframe for last 2 days and sort by datetime"""
    if df_all is not None:
        two_days_ago = now_ist - pd.Timedelta(days=2)
        df_recent = df_all[df_all["datetime"] >= two_days_ago]
        df_recent = df_recent.sort_values("datetime", ascending=False).reset_index(drop=True)
        return df_all, df_recent, two_days_ago
    return None, None, None

def save_changes_to_sheet(sheet, df, df_recent, edited_df, two_days_ago, ist):
    """Save edited dataframe changes back to Google Sheet"""
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
        
        return True  # Changes saved
    else:
        return False  # No changes

def calculate_daily_summaries(df, tz, days=3):
    """
    Returns a list of daily summaries for the last `days` days.
    Sleep intervals spanning midnight are split between days.
    """
    import pandas as pd
    from datetime import timedelta

    if df is None or len(df) == 0:
        return []

    # Ensure datetime is sorted
    df = df.sort_values("datetime")

    # Get the last N days (including today)
    today = pd.Timestamp.now(tz).normalize()
    date_range = [today - timedelta(days=i) for i in range(days)]
    date_range = sorted(date_range)

    summaries = []

    for day in date_range[::-1]:  # reverse for most recent first
        day_start = day
        day_end = day + timedelta(days=1)

        # Filter actions for the day
        day_df = df[(df["datetime"] >= day_start) & (df["datetime"] < day_end)]

        fed_count = (day_df["Action"] == "Fed").sum()
        solid_count = (day_df["Action"] == "Solid Food").sum()
        diaper_count = (day_df["Action"] == "Diaper Change").sum()

        # Sleep calculation
        slept_events = df[df["Action"] == "Slept"]
        woke_events = df[df["Action"] == "Woke Up"]

        sleep_total = timedelta(0)

        # Pair slept/woke events
        slept_times = slept_events["datetime"].tolist()
        woke_times = woke_events["datetime"].tolist()

        pairs = []
        i, j = 0, 0
        while i < len(slept_times):
            slept_time = slept_times[i]
            # Find the next woke_time after slept_time
            while j < len(woke_times) and woke_times[j] <= slept_time:
                j += 1
            if j < len(woke_times):
                woke_time = woke_times[j]
                pairs.append((slept_time, woke_time))
                i += 1
                j += 1
            else:
                # No matching woke_time, assume still sleeping
                i += 1

        # For each pair, split sleep across days
        for slept_time, woke_time in pairs:
            # If sleep interval overlaps with this day
            interval_start = max(slept_time, day_start)
            interval_end = min(woke_time, day_end)
            if interval_start < interval_end:
                sleep_total += (interval_end - interval_start)

        # Format sleep as hours/minutes
        sleep_hours = int(sleep_total.total_seconds() // 3600)
        sleep_minutes = int((sleep_total.total_seconds() % 3600) // 60)
        sleep_str = f"{sleep_hours}h {sleep_minutes}m"

        summaries.append({
            "Date": day.strftime("%d-%b"),
            "Fed": fed_count,
            "Solid Food": solid_count,
            "Diaper": diaper_count,
            "Sleep": sleep_str
        })

    return summaries

def get_most_recent_activity(df):
    """
    Returns the most recent activity and its timestamp from the dataframe.
    If no activity is found, returns (None, None).
    """
    if df is not None and len(df) > 0:
        last_row = df.sort_values("datetime", ascending=False).iloc[0]
        return last_row["Action"], last_row["datetime"]
    return None, None

def fill_missing_sleep_wake_events(df: pd.DataFrame, selected_date: str) -> pd.DataFrame:
    """
    Fill missing 'slept' or 'woke up' events at the start and end of a given day.
    
    Args:
        df: DataFrame containing all activity data with columns: Date, Time, Action, Note, datetime
        selected_date: Date string to filter and process (format should match df['Date'])
    
    Returns:
        DataFrame with added sleep/wake events at day boundaries if needed
    """
    df_single_day = df[df['Date'] == selected_date].copy()
    
    # Ensure correct order by time
    df_single_day = df_single_day.sort_values(by='datetime', ascending=True).reset_index(drop=True)
    
    # Check for missing "slept" or "woke up" at start/end of day (only among slept/woke up events)
    if len(df_single_day) > 0:
        slept_woke_df = df_single_day[df_single_day['Action'].str.lower().isin(['slept', 'woke up'])].copy()
        if not slept_woke_df.empty:
            # Start of day
            first_sw_action = slept_woke_df.iloc[0]['Action'].lower()
            first_sw_time = slept_woke_df.iloc[0]['datetime']
            midnight = first_sw_time.replace(hour=0, minute=0, second=0, microsecond=0)
            if first_sw_action == "woke up":
                new_row = slept_woke_df.iloc[0].copy()
                new_row['datetime'] = midnight
                new_row['Time'] = "00:00:00"
                new_row['Action'] = "slept"
                new_row['Note'] = ""
                df_single_day = pd.concat([pd.DataFrame([new_row]), df_single_day], ignore_index=True)
            elif first_sw_action == "slept":
                new_row = slept_woke_df.iloc[0].copy()
                new_row['datetime'] = midnight
                new_row['Time'] = "00:00:00"
                new_row['Action'] = "woke up"
                new_row['Note'] = ""
                df_single_day = pd.concat([pd.DataFrame([new_row]), df_single_day], ignore_index=True)

            # End of day
            last_sw_action = slept_woke_df.iloc[-1]['Action'].lower()
            last_sw_time = slept_woke_df.iloc[-1]['datetime']
            end_of_day = last_sw_time.replace(hour=23, minute=59, second=59, microsecond=0)
            if last_sw_action == "slept":
                new_row = slept_woke_df.iloc[-1].copy()
                new_row['datetime'] = end_of_day
                new_row['Time'] = "23:59:59"
                new_row['Action'] = "woke up"
                new_row['Note'] = ""
                df_single_day = pd.concat([df_single_day, pd.DataFrame([new_row])], ignore_index=True)
            elif last_sw_action == "woke up":
                new_row = slept_woke_df.iloc[-1].copy()
                new_row['datetime'] = end_of_day
                new_row['Time'] = "23:59:59"
                new_row['Action'] = "slept"
                new_row['Note'] = ""
                df_single_day = pd.concat([df_single_day, pd.DataFrame([new_row])], ignore_index=True)
    
    return df_single_day
