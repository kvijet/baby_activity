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
    
    # Debugging steps (collapsible)
    with st.expander("🛠 Debugging Steps", expanded=False):
        st.write("This section is for debugging and inspection of the filtered data.")
        st.dataframe(filtered_df, hide_index=True, use_container_width=True)

    
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
