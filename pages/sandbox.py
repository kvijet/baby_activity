import streamlit as st
import pytz
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from datetime import time
from utils import (
    load_sheet_data,
    initialize_google_sheets,
    process_dataframe,
    load_css,
    fill_missing_sleep_wake_events
)
from timeline_chart import create_24hour_timeline

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
    
    # Create dictionary of dataframes for last 8 days
    st.subheader("📅 Last 8 Days Data Summary")
    
    # Get available dates
    all_dates = sorted(df_all['Date'].unique(), reverse=True)
    
    # Get yesterday and previous 7 days (total 8 days)
    yesterday = (now_ist - timedelta(days=1)).strftime('%Y-%m-%d')
    eight_days_ago = (now_ist - timedelta(days=8)).strftime('%Y-%m-%d')
    
    # Filter dates from yesterday to 8 days ago
    date_range = []
    for i in range(1, 9):  # 1 to 8 days ago
        date_str = (now_ist - timedelta(days=i)).strftime('%Y-%m-%d')
        if date_str in all_dates:
            date_range.append(date_str)
    
    # Create dictionary of dataframes
    dataframes_dict = {}
    for date in date_range:
        df_day = fill_missing_sleep_wake_events(df_all, date)
        dataframes_dict[date] = df_day
    
    st.write(f"Created dataframes for {len(dataframes_dict)} days")
    
    # Display summary metrics
    summary_cols = st.columns(4)
    with summary_cols[0]:
        st.metric("Total Days", len(dataframes_dict))
    with summary_cols[1]:
        total_records = sum(len(df) for df in dataframes_dict.values())
        st.metric("Total Records", total_records)
    with summary_cols[2]:
        avg_records = total_records / len(dataframes_dict) if dataframes_dict else 0
        st.metric("Avg Records/Day", f"{avg_records:.1f}")
    with summary_cols[3]:
        st.metric("Date Range", f"{date_range[-1] if date_range else 'N/A'} to {date_range[0] if date_range else 'N/A'}")
    
    st.divider()
    
    # Display each day's data in expandable sections
    for date, df_day in dataframes_dict.items():
        with st.expander(f"📆 {date} ({len(df_day)} records)", expanded=False):
            # Display day statistics
            col1, col2, col3, col4 = st.columns(4)
            
            sleep_count = len(df_day[df_day['Action'].str.lower() == 'slept'])
            wake_count = len(df_day[df_day['Action'].str.lower() == 'woke up'])
            fed_count = len(df_day[df_day['Action'] == 'Fed'])
            diaper_count = len(df_day[df_day['Action'] == 'Diaper Change'])
            
            with col1:
                st.metric("Sleep/Wake Events", f"{sleep_count}/{wake_count}")
            with col2:
                st.metric("Fed", fed_count)
            with col3:
                st.metric("Diaper Changes", diaper_count)
            with col4:
                st.metric("Total Activities", len(df_day))
            
            # Display the dataframe
            st.dataframe(
                df_day.sort_values(by='datetime', ascending=False)[['Date', 'Time', 'Action', 'Note']], 
                hide_index=True, 
                use_container_width=True
            )
    
    st.divider()
    
    # Single day data view
    st.subheader("📅 View Data for a Single Day")
    available_dates = sorted(df_all['Date'].unique(), reverse=True)
    selected_day = st.selectbox("Select a date to view", options=available_dates)
    
    # Use the utility function to fill missing sleep/wake events
    df_single_day = fill_missing_sleep_wake_events(df_all, selected_day)

    st.write(f"Showing {len(df_single_day)} records for {selected_day}")
    st.dataframe(df_single_day.sort_values(by='datetime', ascending=False)[['Date', 'Time', 'Action', 'Note']], hide_index=True, use_container_width=True)
    
    # Analysis: Sleep durations and activity intervals
    st.subheader("📊 Activity Analysis")
    
    # Sort by datetime for analysis
    df_analysis = df_single_day.sort_values(by='datetime', ascending=True).copy()
    
    # Sleep Duration Analysis
    st.markdown("**😴 Sleep Durations**")
    sleep_pairs = []
    current_sleep_start = None
    
    # build sleep pairs (keep raw datetimes for classification)
    sleep_pairs = []
    current_sleep_start = None

    for idx, row in df_analysis.iterrows():
        if row['Action'].lower() == 'slept':
            current_sleep_start = row['datetime']
        elif row['Action'].lower() == 'woke up' and current_sleep_start is not None:
            start_dt = current_sleep_start
            end_dt = row['datetime']
            duration = (end_dt - start_dt).total_seconds()
            sleep_pairs.append({
                'start_dt': start_dt,
                'end_dt': end_dt,
                'duration_seconds': duration
            })
            current_sleep_start = None

    # helper: compute overlap seconds with night window (handles windows that span midnight)
    def night_overlap_seconds(start_dt, end_dt, night_start_hour=22, night_end_hour=7):
        total = 0
        # consider candidate night windows for days spanning the sleep period
        day0 = (start_dt.date() - timedelta(days=1))
        dayN = (end_dt.date() + timedelta(days=1))
        cur = day0
        while cur <= dayN:
            if night_end_hour <= night_start_hour:
                window_start = datetime.combine(cur, time(hour=night_start_hour, minute=0, tzinfo=start_dt.tzinfo))
                window_end = datetime.combine(cur + timedelta(days=1), time(hour=night_end_hour, minute=0, tzinfo=start_dt.tzinfo))
            else:
                window_start = datetime.combine(cur, time(hour=night_start_hour, minute=0, tzinfo=start_dt.tzinfo))
                window_end = datetime.combine(cur, time(hour=night_end_hour, minute=0, tzinfo=start_dt.tzinfo))
            overlap_start = max(start_dt, window_start)
            overlap_end = min(end_dt, window_end)
            if overlap_end > overlap_start:
                total += (overlap_end - overlap_start).total_seconds()
            cur += timedelta(days=1)
        return total
    
    # helper: check if a datetime is in night window
    def is_in_night_window(dt, night_start_hour=22, night_end_hour=7):
        hour = dt.hour
        if night_end_hour <= night_start_hour:
            # window spans midnight (e.g., 22:00 to 7:00)
            return hour >= night_start_hour or hour < night_end_hour
        else:
            # window within same day
            return night_start_hour <= hour < night_end_hour

    # classify using hybrid rules and save night sleep windows
    classified = []
    night_sleep_windows = []  # Save for later use
    
    for p in sleep_pairs:
        dur_h = p['duration_seconds'] / 3600.0
        overlap_sec = night_overlap_seconds(p['start_dt'], p['end_dt'])
        overlap_ratio = overlap_sec / p['duration_seconds'] if p['duration_seconds'] > 0 else 0

        # rules (tune thresholds as needed):
        # - if majority of sleep is in night window -> night
        # - OR if very long (>= 3.0h) and overlaps night at all -> night
        # - otherwise -> nap
        is_night = False
        if overlap_ratio >= 0.5:
            is_night = True
        elif dur_h >= 3.0 and overlap_ratio > 0.0:
            is_night = True
        else:
            is_night = False

        if is_night:
            night_sleep_windows.append({
                'start': p['start_dt'],
                'end': p['end_dt']
            })

        classified.append({
            'Slept At': p['start_dt'].strftime('%I:%M %p'),
            'Woke Up At': p['end_dt'].strftime('%I:%M %p'),
            'Duration (h:m)': f"{int(dur_h)}h {int((dur_h % 1)*60)}m",
            'Duration (hours)': f"{dur_h:.2f}",
            'Overlap with night (%)': f"{overlap_ratio*100:.0f}%",
            'Type': 'Night Sleep' if is_night else 'Nap'
        })

    if classified:
        sleep_df = pd.DataFrame(classified)
        # Use column_config to control widths
        st.dataframe(
            sleep_df, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "Slept At": st.column_config.TextColumn(width="small"),
                "Woke Up At": st.column_config.TextColumn(width="small"),
                "Duration (h:m)": st.column_config.TextColumn(width="small"),
                "Duration (hours)": st.column_config.TextColumn(width="small"),
                "Overlap with night (%)": st.column_config.TextColumn(width="small"),
                "Type": st.column_config.TextColumn(width="small")
            }
        )

        total_sleep_hours = sum(float(p['Duration (hours)']) for p in sleep_df.to_dict('records'))
        night_sleep_count = len([p for p in classified if p['Type'] == 'Night Sleep'])
        nap_count = len([p for p in classified if p['Type'] == 'Nap'])
        st.caption(f"Total Sleep: {int(total_sleep_hours)}h {int((total_sleep_hours % 1) * 60)}m | Night Sleep: {night_sleep_count} | Naps: {nap_count}")
    else:
        st.info("No complete sleep cycles found")
    
    st.divider()
    
    # Helper function to classify interval as day or night
    def classify_interval_time(dt):
        """Classify if datetime is during day or night based on sleep windows and time"""
        # First check if it's during a night sleep window
        for window in night_sleep_windows:
            if window['start'] <= dt <= window['end']:
                return 'Night'
        # Otherwise check if it's in typical night hours
        if is_in_night_window(dt):
            return 'Night'
        return 'Day'
    
    # Solid Food Intervals with Day/Night Classification
    st.markdown("**🥘 Time Between Solid Food (Day vs Night)**")
    solid_food_times = df_analysis[df_analysis['Action'] == 'Solid Food']['datetime'].tolist()
    
    if len(solid_food_times) > 1:
        solid_food_intervals = []
        day_intervals = []
        night_intervals = []
        
        for i in range(1, len(solid_food_times)):
            interval = solid_food_times[i] - solid_food_times[i-1]
            hours = interval.total_seconds() / 3600
            time_classification = classify_interval_time(solid_food_times[i])
            
            interval_data = {
                'From': solid_food_times[i-1].strftime('%I:%M %p'),
                'To': solid_food_times[i].strftime('%I:%M %p'),
                'Interval': f"{int(hours)}h {int((hours % 1) * 60)}m",
                'Time': time_classification
            }
            solid_food_intervals.append(interval_data)
            
            if time_classification == 'Day':
                day_intervals.append(hours)
            else:
                night_intervals.append(hours)
        
        solid_food_df = pd.DataFrame(solid_food_intervals)
        st.dataframe(
            solid_food_df, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "From": st.column_config.TextColumn(width="medium"),
                "To": st.column_config.TextColumn(width="medium"),
                "Interval": st.column_config.TextColumn(width="medium"),
                "Time": st.column_config.TextColumn(width="small")
            }
        )
        
        # Summary with day/night breakdown
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Feedings", len(solid_food_times))
        with col2:
            if day_intervals:
                st.metric("Day Avg Interval", f"{sum(day_intervals)/len(day_intervals):.2f}h")
            else:
                st.metric("Day Avg Interval", "N/A")
        with col3:
            if night_intervals:
                st.metric("Night Avg Interval", f"{sum(night_intervals)/len(night_intervals):.2f}h")
            else:
                st.metric("Night Avg Interval", "N/A")
    elif len(solid_food_times) == 1:
        st.info(f"Only one solid food event at {solid_food_times[0].strftime('%I:%M %p')}")
    else:
        st.info("No solid food events found")
    
    st.divider()
    
    # Fed Intervals with Day/Night Classification
    st.markdown("**🍼 Time Between Feeds (Day vs Night)**")
    fed_times = df_analysis[df_analysis['Action'] == 'Fed']['datetime'].tolist()
    
    if len(fed_times) > 1:
        fed_intervals = []
        day_intervals = []
        night_intervals = []
        
        for i in range(1, len(fed_times)):
            interval = fed_times[i] - fed_times[i-1]
            hours = interval.total_seconds() / 3600
            time_classification = classify_interval_time(fed_times[i])
            
            interval_data = {
                'From': fed_times[i-1].strftime('%I:%M %p'),
                'To': fed_times[i].strftime('%I:%M %p'),
                'Interval': f"{int(hours)}h {int((hours % 1) * 60)}m",
                'Time': time_classification
            }
            fed_intervals.append(interval_data)
            
            if time_classification == 'Day':
                day_intervals.append(hours)
            else:
                night_intervals.append(hours)
        
        fed_df = pd.DataFrame(fed_intervals)
        st.dataframe(
            fed_df, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "From": st.column_config.TextColumn(width="medium"),
                "To": st.column_config.TextColumn(width="medium"),
                "Interval": st.column_config.TextColumn(width="medium"),
                "Time": st.column_config.TextColumn(width="small")
            }
        )
        
        # Summary with day/night breakdown
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Feeds", len(fed_times))
        with col2:
            if day_intervals:
                st.metric("Day Avg Interval", f"{sum(day_intervals)/len(day_intervals):.2f}h")
            else:
                st.metric("Day Avg Interval", "N/A")
        with col3:
            if night_intervals:
                st.metric("Night Avg Interval", f"{sum(night_intervals)/len(night_intervals):.2f}h")
            else:
                st.metric("Night Avg Interval", "N/A")
    elif len(fed_times) == 1:
        st.info(f"Only one feed event at {fed_times[0].strftime('%I:%M %p')}")
    else:
        st.info("No feed events found")
    
    st.divider()
    
    # Diaper Change Intervals with Day/Night Classification
    st.markdown("**🚼 Time Between Diaper Changes (Day vs Night)**")
    diaper_times = df_analysis[df_analysis['Action'] == 'Diaper Change']['datetime'].tolist()
    
    if len(diaper_times) > 1:
        diaper_intervals = []
        day_intervals = []
        night_intervals = []
        
        for i in range(1, len(diaper_times)):
            interval = diaper_times[i] - diaper_times[i-1]
            hours = interval.total_seconds() / 3600
            time_classification = classify_interval_time(diaper_times[i])
            
            interval_data = {
                'From': diaper_times[i-1].strftime('%I:%M %p'),
                'To': diaper_times[i].strftime('%I:%M %p'),
                'Interval': f"{int(hours)}h {int((hours % 1) * 60)}m",
                'Time': time_classification
            }
            diaper_intervals.append(interval_data)
            
            if time_classification == 'Day':
                day_intervals.append(hours)
            else:
                night_intervals.append(hours)
        
        diaper_df = pd.DataFrame(diaper_intervals)
        st.dataframe(
            diaper_df, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "From": st.column_config.TextColumn(width="medium"),
                "To": st.column_config.TextColumn(width="medium"),
                "Interval": st.column_config.TextColumn(width="medium"),
                "Time": st.column_config.TextColumn(width="small")
            }
        )
        
        # Summary with day/night breakdown
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Changes", len(diaper_times))
        with col2:
            if day_intervals:
                st.metric("Day Avg Interval", f"{sum(day_intervals)/len(day_intervals):.2f}h")
            else:
                st.metric("Day Avg Interval", "N/A")
        with col3:
            if night_intervals:
                st.metric("Night Avg Interval", f"{sum(night_intervals)/len(night_intervals):.2f}h")
            else:
                st.metric("Night Avg Interval", "N/A")
    elif len(diaper_times) == 1:
        st.info(f"Only one diaper change event at {diaper_times[0].strftime('%I:%M %p')}")
    else:
        st.info("No diaper change events found")
    
    # 24-hour Timeline Visualization
    st.subheader("⏰ 24-Hour Timeline")
    
    fig = create_24hour_timeline(df_single_day)
    st.plotly_chart(fig, use_container_width=True)


# if df_all is not None and len(df_all) > 0:
#     # Filter for last 3 days
#     three_days_ago = now_ist - timedelta(days=3)
#     df_last_3_days = df_all[df_all['datetime'] >= three_days_ago].copy()
    
#     st.subheader(f"📅 Data from Last 3 Days ({len(df_last_3_days)} records)")
    
#     # Display basic statistics
#     col1, col2, col3 = st.columns(3)
#     with col1:
#         st.metric("Total Records", len(df_last_3_days))
#     with col2:
#         st.metric("Date Range", f"{df_last_3_days['datetime'].min().strftime('%d-%b')} to {df_last_3_days['datetime'].max().strftime('%d-%b')}")
#     with col3:
#         st.metric("Activity Types", df_last_3_days['Action'].nunique())
    
#     st.divider()
    
#     # Activity breakdown
#     st.subheader("📊 Activity Breakdown")
#     activity_counts = df_last_3_days['Action'].value_counts()
    
#     col1, col2 = st.columns(2)
#     with col1:
#         st.bar_chart(activity_counts)
#     with col2:
#         st.dataframe(activity_counts.reset_index().rename(columns={'index': 'Activity', 'Action': 'Count'}), hide_index=True)
    
#     st.divider()
    
#     # Raw data display with filters
#     st.subheader("🔍 Filtered Data View")
    
#     # Filters
#     col1, col2 = st.columns(2)
#     with col1:
#         selected_actions = st.multiselect(
#             "Filter by Activity",
#             options=df_last_3_days['Action'].unique().tolist(),
#             default=df_last_3_days['Action'].unique().tolist()
#         )
#     with col2:
#         selected_dates = st.multiselect(
#             "Filter by Date",
#             options=sorted(df_last_3_days['Date'].unique().tolist(), reverse=True),
#             default=sorted(df_last_3_days['Date'].unique().tolist(), reverse=True)
#         )
    
#     # Apply filters
#     filtered_df = df_last_3_days[
#         (df_last_3_days['Action'].isin(selected_actions)) &
#         (df_last_3_days['Date'].isin(selected_dates))
#     ]
    
#     st.write(f"Showing {len(filtered_df)} records")
    

    
#    # Display data - sort first, then select columns (use 'Note' not 'Notes')
#     display_df = filtered_df.sort_values(by='datetime', ascending=False)[['Date', 'Time', 'Action', 'Note']]
#     st.dataframe(display_df, hide_index=True, use_container_width=True)
    
#     st.divider()
    
#     # Export option
#     st.subheader("💾 Export Data")
#     csv = filtered_df.to_csv(index=False)
#     st.download_button(
#         label="Download Filtered Data as CSV",
#         data=csv,
#         file_name=f"baby_activity_last_3_days_{now_ist.strftime('%Y%m%d')}.csv",
#         mime="text/csv"
#     )
    
# else:
#     st.info("No activity data available yet.")
