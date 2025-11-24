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
    current_sleep_start = None
    
    for idx, row in df_timeline.iterrows():
        if row['Action'].lower() == 'slept':
            current_sleep_start = row['datetime']
        elif row['Action'].lower() == 'woke up' and current_sleep_start is not None:
            sleep_periods.append({
                'start': current_sleep_start,
                'end': row['datetime']
            })
            current_sleep_start = None
    
    # Add sleep periods as horizontal bars (all on same line)
    for i, period in enumerate(sleep_periods):
        start_time = period['start'].hour + period['start'].minute/60 + period['start'].second/3600
        end_time = period['end'].hour + period['end'].minute/60 + period['end'].second/3600
        duration = end_time - start_time
        
        fig.add_trace(go.Bar(
            x=[duration],
            y=['Sleep'],
            base=start_time,
            orientation='h',
            marker=dict(color='lightblue', opacity=0.6),
            name='Sleep Period' if i == 0 else '',
            showlegend=(i == 0),
            hovertemplate=f"Sleep: {period['start'].strftime('%I:%M %p')} - {period['end'].strftime('%I:%M %p')}<br>Duration: {int(duration)}h {int((duration % 1) * 60)}m<extra></extra>"
        ))
    
    # Add other activities as markers (all on same line)
    other_activities = df_timeline[~df_timeline['Action'].str.lower().isin(['slept', 'woke up'])].copy()
    
    # Color mapping for different activities
    activity_colors = {
        'Fed': 'green',
        'Solid Food': 'orange',
        'Diaper Change': 'brown',
        'Potty': 'purple',
        'Water': 'blue'
    }
    
    if not other_activities.empty:
        for activity_type in other_activities['Action'].unique():
            activity_data = other_activities[other_activities['Action'] == activity_type]
            times = activity_data['datetime'].dt.hour + activity_data['datetime'].dt.minute/60 + activity_data['datetime'].dt.second/3600
            
            fig.add_trace(go.Scatter(
                x=times.tolist(),
                y=['Activities'] * len(times),
                mode='markers',
                marker=dict(
                    size=15,
                    color=activity_colors.get(activity_type, 'gray'),
                    symbol='circle',
                    line=dict(width=2, color='white')
                ),
                name=activity_type,
                text=[f"{activity_type}<br>{dt.strftime('%I:%M %p')}" for dt in activity_data['datetime']],
                hovertemplate='%{text}<extra></extra>'
            ))
    
    # Update layout
    fig.update_layout(
        title=f"24-Hour Timeline for {selected_day}",
        xaxis=dict(
            title="Time of Day",
            tickmode='array',
            range=[0, 24],
            tickvals=[0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24],
            ticktext=['00:00', '02:00', '04:00', '06:00', '08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00', '22:00', '24:00'],
            showgrid=True,
            gridcolor='lightgray'
        ),
        yaxis=dict(
            title="",
            categoryorder='array',
            categoryarray=['Activities', 'Sleep'],
            showgrid=False
        ),
        height=300,
        hovermode='closest',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
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
