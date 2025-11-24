import streamlit as st
import pytz
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from utils import (
    load_sheet_data,
    initialize_google_sheets,
    process_dataframe,
    load_css,
    fill_missing_sleep_wake_events
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
    
    # 24-hour Timeline Visualization
    st.subheader("⏰ 24-Hour Timeline")
    
    # Sort by datetime for timeline
    df_timeline = df_single_day.sort_values(by='datetime', ascending=True).copy()
    
    # Create figure
    fig = go.Figure()
    
    # Process sleep periods (Gantt chart bars)
    sleep_periods = []
    awake_periods = []
    current_sleep_start = None
    previous_time = None
    
    for idx, row in df_timeline.iterrows():
        if row['Action'].lower() == 'slept':
            # If there was a previous woke up time, this is an awake period
            if previous_time is not None:
                awake_periods.append({
                    'start': previous_time,
                    'end': row['datetime']
                })
            current_sleep_start = row['datetime']
            previous_time = None
        elif row['Action'].lower() == 'woke up' and current_sleep_start is not None:
            sleep_periods.append({
                'start': current_sleep_start,
                'end': row['datetime']
            })
            previous_time = row['datetime']
            current_sleep_start = None
    
    # Add awake periods (Matrix green)
    for i, period in enumerate(awake_periods):
        start_time = period['start'].hour + period['start'].minute/60 + period['start'].second/3600
        end_time = period['end'].hour + period['end'].minute/60 + period['end'].second/3600
        duration = end_time - start_time
        
        fig.add_trace(go.Bar(
            x=[duration],
            y=['Timeline'],
            base=start_time,
            orientation='h',
            marker=dict(color='rgba(0, 255, 65, 0.3)', line=dict(color='rgba(0, 255, 65, 0.8)', width=1)),
            name='Awake' if i == 0 else '',
            showlegend=(i == 0),
            hovertemplate=f"Awake: {period['start'].strftime('%I:%M %p')} - {period['end'].strftime('%I:%M %p')}<br>Duration: {int(duration)}h {int((duration % 1) * 60)}m<extra></extra>"
        ))
    
    # Add sleep periods (Matrix dark with neon outline)
    for i, period in enumerate(sleep_periods):
        start_time = period['start'].hour + period['start'].minute/60 + period['start'].second/3600
        end_time = period['end'].hour + period['end'].minute/60 + period['end'].second/3600
        duration = end_time - start_time
        
        fig.add_trace(go.Bar(
            x=[duration],
            y=['Timeline'],
            base=start_time,
            orientation='h',
            marker=dict(color='rgba(0, 20, 40, 0.8)', line=dict(color='rgba(0, 255, 255, 0.6)', width=2)),
            name='Sleep' if i == 0 else '',
            showlegend=(i == 0),
            hovertemplate=f"Sleep: {period['start'].strftime('%I:%M %p')} - {period['end'].strftime('%I:%M %p')}<br>Duration: {int(duration)}h {int((duration % 1) * 60)}m<extra></extra>"
        ))
    
    # Add other activities as markers positioned in middle of timeline bar
    other_activities = df_timeline[~df_timeline['Action'].str.lower().isin(['slept', 'woke up'])].copy()
    
    # Matrix-themed color mapping for different activities
    activity_colors = {
        'Fed': '#00FF41',  # Matrix green
        'Solid Food': '#FF6EC7',  # Neon pink
        'Diaper Change': '#FFD700',  # Gold
        'Potty': '#00FFFF',  # Cyan
        'Water': '#8A2BE2'  # Blue violet
    }
    
    if not other_activities.empty:
        for activity_type in other_activities['Action'].unique():
            activity_data = other_activities[other_activities['Action'] == activity_type]
            times = activity_data['datetime'].dt.hour + activity_data['datetime'].dt.minute/60 + activity_data['datetime'].dt.second/3600
            
            fig.add_trace(go.Scatter(
                x=times.tolist(),
                y=['Timeline'] * len(times),
                mode='markers+text',
                marker=dict(
                    size=18,
                    color=activity_colors.get(activity_type, '#FFFFFF'),
                    symbol='circle',
                    line=dict(width=3, color='rgba(0, 0, 0, 0.8)')
                ),
                text=['●'] * len(times),
                textposition='middle center',
                textfont=dict(size=20, color=activity_colors.get(activity_type, '#FFFFFF')),
                name=activity_type,
                hovertext=[f"{activity_type}<br>{dt.strftime('%I:%M %p')}" for dt in activity_data['datetime']],
                hovertemplate='%{hovertext}<extra></extra>'
            ))
    
    # Update layout with Matrix theme
    fig.update_layout(
        title=dict(
            text=f"24-Hour Timeline for {selected_day}",
            font=dict(color='#00FF41', size=20)
        ),
        paper_bgcolor='rgba(0, 10, 20, 1)',
        plot_bgcolor='rgba(0, 0, 0, 0.9)',
        xaxis=dict(
            title=dict(text="Time of Day", font=dict(color='#00FF41')),
            tickmode='array',
            range=[0, 24],
            tickvals=[0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24],
            ticktext=['00:00', '02:00', '04:00', '06:00', '08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00', '22:00', '24:00'],
            showgrid=True,
            gridcolor='rgba(0, 255, 65, 0.2)',
            tickfont=dict(color='#00FF41')
        ),
        yaxis=dict(
            title="",
            showticklabels=False,
            showgrid=False
        ),
        height=250,
        hovermode='closest',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color='#00FF41'),
            bgcolor='rgba(0, 0, 0, 0.7)'
        ),
        barmode='overlay',
        bargap=0
    )
    
    st.plotly_chart(fig, use_container_width=True)


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
