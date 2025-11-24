import streamlit as st
import pytz
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from utils import (
    load_sheet_data,
    initialize_google_sheets,
    process_dataframe,
    load_css
)

st.set_page_config(
    page_title="Sandbox - Suddu Tracker 👶",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Load custom CSS
load_css(Path(__file__).parent.parent)

st.title("🔬 Sandbox - Exploratory Data Analysis")

# Initialize Google Sheets
creds_dict = st.secrets["service_account"]
sheet = initialize_google_sheets(creds_dict)

# Load all data
try:
    data = load_sheet_data(sheet)
except Exception as e:
    st.error(f"Failed to connect to Google Sheets: {str(e)}")
    st.stop()

ist = pytz.timezone('Asia/Kolkata')
now_ist = datetime.now(ist)

# Process data
df_all = process_dataframe(data, ist)

# Debugging steps (collapsible)
with st.expander("🛠 Debugging Steps", expanded=False):
    st.write("This section is for debugging and inspection of the filtered data.")
    st.dataframe(df_all, hide_index=True, use_container_width=True)

    # Single day data view
    st.subheader("📅 View Data for a Single Day")
    available_dates = sorted(df_all['Date'].unique(), reverse=True)
    selected_day = st.selectbox("Select a date to view", options=available_dates)
    df_single_day = df_all[df_all['Date'] == selected_day].copy()

    # Ensure correct order by time
    df_single_day = df_single_day.sort_values(by='datetime', ascending=True).reset_index(drop=True)

    # Check for missing "slept" or "woke up" at start of day
    if len(df_single_day) > 0:
        first_action = df_single_day.iloc[0]['Action'].lower()
        first_time = df_single_day.iloc[0]['datetime']
        midnight = first_time.replace(hour=0, minute=0, second=0, microsecond=0)

        # If first action is "woke up" before any "slept", add "slept" at midnight
        if first_action == "woke up":
            new_row = df_single_day.iloc[0].copy()
            new_row['datetime'] = midnight
            new_row['Time'] = "00:00:00"
            new_row['Action'] = "slept"
            new_row['Note'] = ""
            df_single_day = pd.concat([pd.DataFrame([new_row]), df_single_day], ignore_index=True)
        # If first action is "slept" before any "woke up", add "woke up" at midnight
        elif first_action == "slept":
            new_row = df_single_day.iloc[0].copy()
            new_row['datetime'] = midnight
            new_row['Time'] = "00:00:00"
            new_row['Action'] = "woke up"
            new_row['Note'] = ""
            df_single_day = pd.concat([pd.DataFrame([new_row]), df_single_day], ignore_index=True)

        # Check for missing "slept" or "woke up" at end of day
        last_action = df_single_day.iloc[-1]['Action'].lower()
        last_time = df_single_day.iloc[-1]['datetime']
        end_of_day = last_time.replace(hour=23, minute=59, second=59, microsecond=0)

        # If last action is "slept", add "woke up" at 23:59:59
        if last_action == "slept":
            new_row = df_single_day.iloc[-1].copy()
            new_row['datetime'] = end_of_day
            new_row['Time'] = "23:59:59"
            new_row['Action'] = "woke up"
            new_row['Note'] = ""
            df_single_day = pd.concat([df_single_day, pd.DataFrame([new_row])], ignore_index=True)
        # If last action is "woke up", add "slept" at 23:59:59
        elif last_action == "woke up":
            new_row = df_single_day.iloc[-1].copy()
            new_row['datetime'] = end_of_day
            new_row['Time'] = "23:59:59"
            new_row['Action'] = "slept"
            new_row['Note'] = ""
            df_single_day = pd.concat([df_single_day, pd.DataFrame([new_row])], ignore_index=True)

    st.write(f"Showing {len(df_single_day)} records for {selected_day}")
    st.dataframe(df_single_day.sort_values(by='datetime', ascending=False)[['Date', 'Time', 'Action', 'Note']], hide_index=True, use_container_width=True)


if df_all is not None and len(df_all) > 0:
    # Filter for last 3 days
    three_days_ago = now_ist - timedelta(days=3)
    df_last_3_days = df_all[df_all['datetime'] >= three_days_ago].copy()
    
    st.subheader(f"📅 Data from Last 3 Days ({len(df_last_3_days)} records)")
    
    # Display basic statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Records", len(df_last_3_days))
    with col2:
        st.metric("Date Range", f"{df_last_3_days['datetime'].min().strftime('%d-%b')} to {df_last_3_days['datetime'].max().strftime('%d-%b')}")
    with col3:
        st.metric("Activity Types", df_last_3_days['Action'].nunique())
    
    st.divider()
    
    # Activity breakdown
    st.subheader("📊 Activity Breakdown")
    activity_counts = df_last_3_days['Action'].value_counts()
    
    col1, col2 = st.columns(2)
    with col1:
        st.bar_chart(activity_counts)
    with col2:
        st.dataframe(activity_counts.reset_index().rename(columns={'index': 'Activity', 'Action': 'Count'}), hide_index=True)
    
    st.divider()
    
    # Raw data display with filters
    st.subheader("🔍 Filtered Data View")
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        selected_actions = st.multiselect(
            "Filter by Activity",
            options=df_last_3_days['Action'].unique().tolist(),
            default=df_last_3_days['Action'].unique().tolist()
        )
    with col2:
        selected_dates = st.multiselect(
            "Filter by Date",
            options=sorted(df_last_3_days['Date'].unique().tolist(), reverse=True),
            default=sorted(df_last_3_days['Date'].unique().tolist(), reverse=True)
        )
    
    # Apply filters
    filtered_df = df_last_3_days[
        (df_last_3_days['Action'].isin(selected_actions)) &
        (df_last_3_days['Date'].isin(selected_dates))
    ]
    
    st.write(f"Showing {len(filtered_df)} records")
    

    
   # Display data - sort first, then select columns (use 'Note' not 'Notes')
    display_df = filtered_df.sort_values(by='datetime', ascending=False)[['Date', 'Time', 'Action', 'Note']]
    st.dataframe(display_df, hide_index=True, use_container_width=True)
    
    st.divider()
    
    # Export option
    st.subheader("💾 Export Data")
    csv = filtered_df.to_csv(index=False)
    st.download_button(
        label="Download Filtered Data as CSV",
        data=csv,
        file_name=f"baby_activity_last_3_days_{now_ist.strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )
    
else:
    st.info("No activity data available yet.")
