"""
Baby Activity - Quick Actions Streamlit App

Save this file as app.py and run with:
  streamlit run app.py

Quick notes for running in Google Colab:
- Install dependencies:
    !pip install --upgrade pip
    !pip install streamlit pandas pyngrok
- Save this file to /content/app.py (or upload).
- Use pyngrok to create a public URL and start streamlit:
    from pyngrok import ngrok
    public_url = ngrok.connect(8501).public_url
    get_ipython().system_raw("streamlit run /content/app.py --server.port 8501 --server.headless true &")
    print(public_url)

This app provides:
- Section 1: Quick actions (Sleep / Wake, Diaper change, Poop)
- Section 2: Shows the most recent 5 entries recorded by the quick actions

Each quick action records the current timestamp and action label into session state so you can test in Colab.
"""

import streamlit as st
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="Baby Quick Actions", layout="wide")

# --- Helper functions -------------------------------------------------------
def init_session():
    """Initialize session state keys used by the app."""
    if "entries" not in st.session_state:
        # entries is a list of dicts: {"timestamp": ..., "action": ...}
        st.session_state.entries = []
    if "is_sleeping" not in st.session_state:
        # infer sleeping from the last entry if any
        st.session_state.is_sleeping = False
        if st.session_state.entries:
            last = st.session_state.entries[-1]
            if last.get("action") in ("sleep", "sleeping"):
                st.session_state.is_sleeping = True

def add_entry(action_label: str):
    """Record a new entry with current timestamp and action label."""
    ts = datetime.now().isoformat(sep=" ", timespec="seconds")
    st.session_state.entries.append({"timestamp": ts, "action": action_label})
    # keep entries reasonably small in memory (optional)
    if len(st.session_state.entries) > 1000:
        st.session_state.entries = st.session_state.entries[-1000:]


# --- Initialize ----------------------------------------------------------------
init_session()

st.title("Baby Quick Actions")
st.markdown(
    "Use the quick action buttons to record events. The most recent 5 entries are shown below."
)

# Layout: two main sections (quick actions | recent entries)
left, right = st.columns([1, 1])

with left:
    st.header("Quick actions")
    st.caption("Click a button to record the current timestamp and action.")

    # Determine label for sleep button based on state
    sleep_label = "Wake up" if st.session_state.is_sleeping else "Sleep"

    # Buttons placed horizontally
    b1, b2, b3 = st.columns(3)

    with b1:
        if st.button(sleep_label):
            if st.session_state.is_sleeping:
                # Wake up flow
                add_entry("awake")
                st.session_state.is_sleeping = False
                st.success(f"Recorded: awake at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                # Go to sleep flow
                add_entry("sleep")
                st.session_state.is_sleeping = True
                st.success(f"Recorded: sleep at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    with b2:
        if st.button("Diaper change"):
            add_entry("diaper change")
            st.success(f"Recorded: diaper change at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    with b3:
        if st.button("Poop"):
            add_entry("poop")
            st.success(f"Recorded: poop at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    st.markdown("---")
    st.markdown("Session controls")
    sc1, sc2 = st.columns([1, 1])
    with sc1:
        if st.button("Clear recent entries"):
            st.session_state.entries = []
            st.session_state.is_sleeping = False
            st.info("All entries cleared for this session.")
    with sc2:
        if st.button("Add sample entry (feed)"):
            add_entry("feed")
            st.success("Sample 'feed' entry added.")


with right:
    st.header("Recent entries (latest 5)")
    entries = list(st.session_state.entries)  # copy for safety
    if not entries:
        st.info("No entries yet. Use the quick action buttons to record events.")
    else:
        # Show the most recent 5 entries (newest first)
        recent = entries[-5:][::-1]
        df = pd.DataFrame(recent)
        # Ensure nice column order
        df = df[["timestamp", "action"]]
        st.dataframe(df, use_container_width=True)

        # small convenience: download as CSV
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download recent 5 as CSV", data=csv, file_name="recent_5_entries.csv", mime="text/csv")

# Footer note
st.markdown(
    """
    Notes:
    - The Sleep button toggles to 'Wake up' automatically when the session state indicates the last recorded action was 'sleep'.
    - All data is stored only in the Streamlit session (in memory). For persistent storage, connect to a database or push to a remote file.
    - To test in Google Colab, follow the instructions at the top of this file to start Streamlit and expose it with ngrok.
    """
)
