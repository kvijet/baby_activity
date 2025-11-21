import streamlit as st
import pytz
from datetime import datetime
from pathlib import Path
import time
from utils import (
    get_ist_datetime,
    load_sheet_data,
    initialize_google_sheets,
    process_dataframe,
    load_recent_data,
    save_changes_to_sheet,
    load_css,
    calculate_daily_summaries
)

st.set_page_config(
    page_title="Suddu Tracker 👶",
    page_icon="👶",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Load custom CSS
load_css(Path(__file__).parent)

st.title("👶 Suddu Tracker 👶")

# Initialize Google Sheets
creds_dict = st.secrets["service_account"]
sheet = initialize_google_sheets(creds_dict)

# Load all data once at the beginning
try:
    data = load_sheet_data(sheet)
except Exception as e:
    st.error(f"Failed to connect to Google Sheets: {str(e)}")
    data = None

ist = pytz.timezone('Asia/Kolkata')
now_ist = datetime.now(ist)

# Process data
df_all = process_dataframe(data, ist)

# Display time elapsed since key activities
st.subheader("⏱️ Time Since Last Activity")

if df_all is not None and len(df_all) > 0:
    tracked_activities = ['Fed', 'Solid Food', 'Diaper Change']
    cols = st.columns(len(tracked_activities) + 1)

    # Handle Woke Up/Slept logic
    try:
        woke_df = df_all[df_all['Action'] == 'Woke Up']
        slept_df = df_all[df_all['Action'] == 'Slept']
        last_woke = woke_df['datetime'].max() if not woke_df.empty else None
        last_slept = slept_df['datetime'].max() if not slept_df.empty else None

        # Determine which happened most recently
        if last_woke and last_slept:
            if last_woke > last_slept:
                last_activity = 'Woke Up'
                last_time = last_woke
            else:
                last_activity = 'Slept'
                last_time = last_slept
        elif last_woke:
            last_activity = 'Woke Up'
            last_time = last_woke
        elif last_slept:
            last_activity = 'Slept'
            last_time = last_slept
        else:
            last_activity = None
            last_time = None

        with cols[0]:
            if last_time:
                time_diff = now_ist - last_time
                hours = int(time_diff.total_seconds() // 3600)
                minutes = int((time_diff.total_seconds() % 3600) // 60)
                st.metric(label=f"{last_activity}", value=f"{hours}h {minutes}m")
                st.caption(f"📅 {last_time.strftime('%d-%b %I:%M %p')}")
            else:
                st.metric(label="Sleep/Wake", value="No data")
    except Exception:
        with cols[0]:
            st.metric(label="Sleep/Wake", value="Error")

    # Handle other activities
    for i, activity in enumerate(tracked_activities, start=1):
        try:
            activity_df = df_all[df_all['Action'] == activity]
            if not activity_df.empty:
                last_time = activity_df['datetime'].max()
                time_diff = now_ist - last_time
                hours = int(time_diff.total_seconds() // 3600)
                minutes = int((time_diff.total_seconds() % 3600) // 60)
                with cols[i]:
                    st.metric(label=activity, value=f"{hours}h {minutes}m")
                    st.caption(f"📅 {last_time.strftime('%d-%b %I:%M %p')}")
            else:
                with cols[i]:
                    st.metric(label=activity, value="No data")
        except Exception:
            with cols[i]:
                st.metric(label=activity, value="Error")
else:
    st.info("No activity data available yet.")

st.divider()

# Layout: two containers
container1, container2 = st.columns([1, 2])

with container1:
    st.header("Add Activity")
    actions = ['Slept', 'Woke Up', 'Water', 'Fed', 'Solid Food', 'Potty', 'Diaper Change']
    for action in actions:
        if st.button(action, key=f"add_{action}"):
            date, time_str = get_ist_datetime()
            # Find most recent activity
            # Always load latest data from Google Sheet to avoid stale session state
            try:
                latest_data = load_sheet_data(sheet)
                latest_df = process_dataframe(latest_data, ist)
            except Exception as e:
                st.error(f"Failed to reload data: {str(e)}")
                latest_df = None

            if latest_df is not None and len(latest_df) > 0:
                last_row = df_all.iloc[-1]
                last_action = last_row['Action']
                last_time = last_row['datetime']
                if last_action == action:
                    # Duplicate detected, show warning and options
                    # Custom color scheme for action-required section
                    st.markdown(
                        """
                        <div style="background-color:#fff3cd; border:2px solid #ff9800; border-radius:8px; padding:16px; margin-bottom:10px;">
                        <span style="color:#b26a00; font-weight:bold; font-size:16px;">
                        ⚠️ '{action}' was already added at {last_time}.
                        </span>
                        </div>
                        """.format(
                            action=action,
                            last_time=last_time.strftime('%d-%b %I:%M %p')
                        ),
                        unsafe_allow_html=True
                    )
                    col_accept, col_decline = st.columns(2)
                    # Apply button style to both columns

                    with col_accept:
                        accept_btn = st.button(
                            "✅ Accept and Add",
                            key=f"accept_{action}",
                            help="Add anyway",
                        )
                        if accept_btn:
                            new_row = [date, time_str, action, ""]
                            sheet.append_row(new_row)
                            st.success(f"Recorded: {action} at {date} {time_str}")
                            st.rerun()
                    with col_decline:
                        decline_btn = st.button(
                            "❌ Decline",
                            key=f"decline_{action}",
                            help="Do not add"
                        )
                        if decline_btn:
                            st.info("Activity not logged.")
                else:
                    new_row = [date, time_str, action, ""]
                    sheet.append_row(new_row)
                    st.success(f"Recorded: {action} at {date} {time_str}")
            else:
                new_row = [date, time_str, action, ""]
                sheet.append_row(new_row)
                st.success(f"Recorded: {action} at {date} {time_str}")

with container2:
    st.header("Recent Activity")
    
    # Add refresh button
    col_refresh, col_save = st.columns([1, 4])
    with col_refresh:
        if st.button("🔄 Refresh", key="refresh_button"):
            st.rerun()
    
    # Load data
    df, df_recent, two_days_ago = load_recent_data(df_all, now_ist)
    
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
            changes_saved = save_changes_to_sheet(sheet, df, df_recent, edited_df, two_days_ago, ist)
            if changes_saved:
                st.success("Changes saved to Google Sheet!")
                st.session_state["refresh_button"] = True
            else:
                st.info("No changes to save.")
    else:
        st.info("No data found.")

st.divider()

# Daily Summary Section
st.header("📊 Daily Summary (Last 3 Days)")

if df_all is not None and len(df_all) > 0:
    summaries = calculate_daily_summaries(df_all, ist, days=3)
    
    if summaries:
        summary_cols = st.columns(3)
        
        for idx, summary in enumerate(summaries):
            with summary_cols[idx]:
                st.subheader(summary['Date'])
                st.metric("🍼 Fed", summary['Fed'])
                st.metric("🥘 Solid Food", summary['Solid Food'])
                st.metric("🚼 Diaper Changes", summary['Diaper'])
                st.metric("😴 Total Sleep", summary['Sleep'])
    else:
        st.info("No summary data available.")
else:
    st.info("No activity data available yet.")