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

def calculate_daily_summaries(df_all, ist, days=3):
    """Calculate daily summaries for the last N days"""
    if df_all is None or len(df_all) == 0:
        return None
    
    from datetime import datetime, timedelta
    
    now_ist = datetime.now(ist)
    summaries = []
    
    for i in range(days):
        day_date = (now_ist - timedelta(days=i)).date()
        day_df = df_all[df_all['datetime'].dt.date == day_date]
        
        # Count activities
        fed_count = len(day_df[day_df['Action'] == 'Fed'])
        solid_food_count = len(day_df[day_df['Action'] == 'Solid Food'])
        diaper_count = len(day_df[day_df['Action'] == 'Diaper Change'])
        
        # Calculate total sleep duration
        sleep_df = day_df[day_df['Action'].isin(['Slept', 'Woke Up'])].sort_values('datetime')
        total_sleep_minutes = 0
        
        if len(sleep_df) > 0:
            current_sleep_start = None
            for _, row in sleep_df.iterrows():
                if row['Action'] == 'Slept':
                    current_sleep_start = row['datetime']
                elif row['Action'] == 'Woke Up' and current_sleep_start:
                    sleep_duration = (row['datetime'] - current_sleep_start).total_seconds() / 60
                    total_sleep_minutes += sleep_duration
                    current_sleep_start = None
            
            # If still sleeping (no wake up after last sleep)
            if current_sleep_start and i == 0:
                sleep_duration = (now_ist - current_sleep_start).total_seconds() / 60
                total_sleep_minutes += sleep_duration
        
        sleep_hours = int(total_sleep_minutes // 60)
        sleep_mins = int(total_sleep_minutes % 60)
        
        summaries.append({
            'Date': day_date.strftime('%d-%b-%Y'),
            'Fed': fed_count,
            'Solid Food': solid_food_count,
            'Diaper': diaper_count,
            'Sleep': f"{sleep_hours}h {sleep_mins}m"
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
