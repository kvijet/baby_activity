import streamlit as st
import requests
from urllib.parse import urlencode

def get_github_auth_url():
    """Generate GitHub OAuth authorization URL"""
    GITHUB_CLIENT_ID = st.secrets.get("github_oauth", {}).get("client_id", "")
    REDIRECT_URI = st.secrets.get("github_oauth", {}).get("redirect_uri", "http://localhost:8501")
    
    params = {
        'client_id': GITHUB_CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'scope': 'read:user user:email',
        'state': 'random_state_string'
    }
    return f"https://github.com/login/oauth/authorize?{urlencode(params)}"

def exchange_code_for_token(code):
    """Exchange authorization code for access token"""
    GITHUB_CLIENT_ID = st.secrets.get("github_oauth", {}).get("client_id", "")
    GITHUB_CLIENT_SECRET = st.secrets.get("github_oauth", {}).get("client_secret", "")
    REDIRECT_URI = st.secrets.get("github_oauth", {}).get("redirect_uri", "http://localhost:8501")
    
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
    ALLOWED_USERS = st.secrets.get("github_oauth", {}).get("allowed_users", ["kvijet"])
    return username.lower() in [user.lower() for user in ALLOWED_USERS]

def check_authentication():
    """Handle GitHub OAuth callback and authentication"""
    query_params = st.query_params
    
    # Check if we have a code from GitHub callback
    if 'code' in query_params and not st.session_state.get('authenticated', False):
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
    GITHUB_CLIENT_ID = st.secrets.get("github_oauth", {}).get("client_id", "")
    GITHUB_CLIENT_SECRET = st.secrets.get("github_oauth", {}).get("client_secret", "")
    
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
            REDIRECT_URI = st.secrets.get("github_oauth", {}).get("redirect_uri", "http://localhost:8501")
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
        denied_user = st.session_state.get('denied_user', 'Unknown')
        st.warning(f"Sorry, the GitHub user **@{denied_user}** is not authorized to access this application.")
        
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
    if st.session_state.get('user_info'):
        user = st.session_state.user_info
        
        # Create a compact user info bar at the top
        col1, col2, col3 = st.columns([6, 1, 1])

        with col1:
            if user.get('avatar_url') and user.get('name'):
            st.markdown(
                f"""
                <div style="display: flex; align-items: center;">
                <img src="{user['avatar_url']}" width="32" style="border-radius: 50%; margin-right: 8px;">
                <span style="font-weight: 500;">{user['name']}</span>
                </div>
                """,
                unsafe_allow_html=True
            )
        
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

def require_authentication():
    """
    Main authentication guard function.
    Call this at the top of every page that requires authentication.
    """
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_info' not in st.session_state:
        st.session_state.user_info = None
    if 'access_denied' not in st.session_state:
        st.session_state.access_denied = False
    
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
    
    # Show user info in header for authenticated users
    show_user_info()
