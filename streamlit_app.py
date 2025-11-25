import streamlit as st
import pytz
from datetime import datetime
from pathlib import Path
import time
import requests
from urllib.parse import urlencode
from utils import (
    get_ist_datetime,
    load_sheet_data,
    initialize_google_sheets,
    process_dataframe,
    load_recent_data,
    save_changes_to_sheet,
    load_css,
    calculate_daily_summaries,
    get_most_recent_activity
)

st.set_page_config(
    page_title="Suddu Tracker 👶",
    page_icon="👶",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Load custom CSS
load_css(Path(__file__).parent)

# GitHub OAuth Configuration
GITHUB_CLIENT_ID = st.secrets.get("github_oauth", {}).get("client_id", "")
GITHUB_CLIENT_SECRET = st.secrets.get("github_oauth", {}).get("client_secret", "")
REDIRECT_URI = st.secrets.get("github_oauth", {}).get("redirect_uri", "http://localhost:8501")

# Whitelist of allowed GitHub usernames
ALLOWED_USERS = st.secrets.get("github_oauth", {}).get("allowed_users", ["kvijet"])

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_info' not in st.session_state:
    st.session_state.user_info = None
if 'access_denied' not in st.session_state:
    st.session_state.access_denied = False

def get_github_auth_url():
    """Generate GitHub OAuth authorization URL"""
    params = {
        'client_id': GITHUB_CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'scope': 'read:user user:email',
        'state': 'random_state_string'
    }
    return f"https://github.com/login/oauth/authorize?{urlencode(params)}"

def exchange_code_for_token(code):
    """Exchange authorization code for access token"""
    try:
        token_url = "https://github.com/login/oauth/access_token"
        headers = {'Accept': 'application/json'}
        data = {
            'client_id': GITHUB_CLIENT_ID,
            'client_secret': GITHUB_CLIENT_SECRET,
            'code': code,
            'redirect_uri': REDIRECT_URI
        }
        
        response = requests.post(token_url, headers=headers, data=data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if 'access_token' in result:
                return result['access_token']
            elif 'error' in result:
                st.error(f"GitHub OAuth Error: {result.get('error_description', result['error'])}")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Network error during authentication: {str(e)}")
        return None

def get_github_user_info(access_token):
    """Fetch user information from GitHub"""
    try:
        headers = {'Authorization': f'token {access_token}'}
        response = requests.get('https://api.github.com/user', headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Network error fetching user info: {str(e)}")
        return None

def is_user_allowed(username):
    """Check if the GitHub username is in the whitelist"""
    return username.lower() in [user.lower() for user in ALLOWED_USERS]

def check_authentication():
    """Handle GitHub OAuth callback and authentication"""
    query_params = st.query_params
    
    # Check if we have a code from GitHub callback
    if 'code' in query_params and not st.session_state.authenticated:
        code = query_params['code']
        
        # Show processing message
        with st.spinner('Authenticating with GitHub...'):
            access_token = exchange_code_for_token(code)
        
        if access_token:
            with st.spinner('Fetching user information...'):
                user_info = get_github_user_info(access_token)
            
            if user_info:
                username = user_info.get('login')
                
                # Check if user is in whitelist
                if is_user_allowed(username):
                    st.session_state.authenticated = True
                    st.session_state.user_info = user_info
                    st.session_state.access_token = access_token
                    st.session_state.access_denied = False
                    # Clear query params
                    st.query_params.clear()
                    st.rerun()
                else:
                    # User authenticated with GitHub but not authorized
                    st.session_state.access_denied = True
                    st.session_state.denied_user = username
                    st.query_params.clear()
                    st.rerun()
            else:
                st.error("Failed to fetch user information from GitHub. Please try again.")
                if st.button("Retry Login"):
                    st.query_params.clear()
                    st.rerun()
        else:
            st.error("Failed to authenticate with GitHub. Please try again.")
            if st.button("Retry Login"):
                st.query_params.clear()
                st.rerun()
    
    # Handle error parameter from GitHub
    elif 'error' in query_params:
        error = query_params['error']
        error_description = query_params.get('error_description', 'Unknown error')
        st.error(f"GitHub OAuth Error: {error_description}")
        if st.button("Back to Login"):
            st.query_params.clear()
            st.rerun()

def show_login_page():
    """Display login page"""
    st.title("👶 Suddu Tracker 👶")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 🔐 Authentication Required")
        st.info("Please login with your authorized GitHub account to access the baby activity tracker.")
        
        # Check if OAuth is configured
        if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
            st.error("⚠️ GitHub OAuth is not configured. Please contact the administrator.")
            st.stop()
        
        auth_url = get_github_auth_url()
        
        # Use a link button for better compatibility
        st.link_button(
            label="🐙 Login with GitHub",
            url=auth_url,
            use_container_width=True
        )
        
        st.markdown("---")
        st.caption("Only authorized GitHub users can access this application.")
        
        # Show configuration info for debugging (only in development)
        if st.secrets.get("debug_mode", False):
            with st.expander("🔍 Debug Info"):
                st.write("Client ID:", GITHUB_CLIENT_ID[:10] + "..." if GITHUB_CLIENT_ID else "Not set")
                st.write("Redirect URI:", REDIRECT_URI)

def show_access_denied():
    """Display access denied page"""
    st.title("👶 Suddu Tracker 👶")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.error("### 🚫 Access Denied")
        st.warning(f"Sorry, the GitHub user **@{st.session_state.denied_user}** is not authorized to access this application.")
        
        st.markdown("""
        #### What to do:
        - Contact the administrator to request access
        - Make sure you're logging in with the correct GitHub account
        """)
        
        if st.button("🔄 Try Different Account"):
            st.session_state.access_denied = False
            if 'denied_user' in st.session_state:
                del st.session_state.denied_user
            st.rerun()
        
        st.markdown("---")
        st.caption("This application is restricted to authorized users only.")

def show_user_info():
    """Display logged-in user information in header"""
    if st.session_state.user_info:
        user = st.session_state.user_info
        
        # Create a compact user info bar at the top
        col1, col2, col3 = st.columns([6, 1, 1])
        
        with col2:
            if user.get('avatar_url'):
                st.image(user['avatar_url'], width=40)
        
        with col3:
            if st.button("🚪", key="logout_button", help="Logout"):
                st.session_state.authenticated = False
                st.session_state.user_info = None
                st.session_state.access_denied = False
                if 'access_token' in st.session_state:
                    del st.session_state.access_token
                if 'denied_user' in st.session_state:
                    del st.session_state.denied_user
                st.rerun()

# Check authentication status
check_authentication()

# Show access denied page if user is not authorized
if st.session_state.access_denied:
    show_access_denied()
    st.stop()

# Show login page if not authenticated
if not st.session_state.authenticated:
    show_login_page()
    st.stop()

# Show user info in header
show_user_info()

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

    # Get most recent activity and time
    recent_activity, recent_time = get_most_recent_activity(df_all)

    for action in actions:
        if recent_activity == action and recent_time is not None:
            st.caption(f"Last '{action}' recorded at {recent_time.strftime('%d-%b %I:%M %p')}")
        if st.button(action, key=f"add_{action}"):
            date, time_str = get_ist_datetime()
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
                st.rerun()
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