import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json

# Load credentials from Streamlit secrets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

creds_dict = st.secrets["service_account"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

sheet = client.open("Your Sheet Name").sheet1
df = pd.DataFrame(sheet.get_all_records())

st.title("Google Sheet Data")
st.dataframe(df)

# """
# Baby Activity - Quick Actions Streamlit App
# Persist entries to a CSV file inside a GitHub repo using the GitHub Contents API.

# Usage:
# - Put a GitHub Personal Access Token (repo scope) into Streamlit secrets as: {"GITHUB_TOKEN": "ghp_..."}
#   or set environment variable GITHUB_TOKEN.
# - Configure GITHUB_REPO and GITHUB_PATH below (defaults set to this repo and data/entries.csv).
# - The app will attempt to load entries from the CSV at startup and save the CSV after new entries.

# Security note:
# - Keep the token secret. Use Streamlit Cloud secrets or environment variables; don't hard-code tokens.
# - For production/real multi-user use, consider a dedicated backend (database, Google Sheets, S3) rather than committing to the repo.
# """

# import os
# import base64
# import json
# import io
# import requests
# import streamlit as st
# from datetime import datetime, timezone, timedelta
# import pandas as pd

# st.set_page_config(page_title="Baby Quick Actions", layout="wide")

# # Configuration: change these as needed
# GITHUB_REPO = "kvijet/baby_activity"      # owner/repo
# GITHUB_PATH = "data/entries.csv"          # path inside the repo to store CSV
# GITHUB_BRANCH = None  # set to a branch name if needed, else default branch

# # Timezone for IST
# IST = timezone(timedelta(hours=5, minutes=30), name="IST")


# # --- GitHub helper functions -------------------------------------------------
# def get_github_token():
#     # Prefer Streamlit secrets, fall back to environment variable
#     token = None
#     try:
#         token = st.secrets.get("GITHUB_TOKEN")
#     except Exception:
#         token = None
#     if not token:
#         token = os.environ.get("GITHUB_TOKEN")
#     return token


# def github_get_file(repo: str, path: str, token: str, branch: str = None):
#     """
#     Return (content_bytes, sha) or (None, None) if not found.
#     Uses the GitHub Contents API.
#     """
#     headers = {
#         "Accept": "application/vnd.github+json",
#     }
#     if token:
#         headers["Authorization"] = f"token {token}"
#     url = f"https://api.github.com/repos/{repo}/contents/{path}"
#     params = {}
#     if branch:
#         params["ref"] = branch
#     resp = requests.get(url, headers=headers, params=params)
#     if resp.status_code == 200:
#         payload = resp.json()
#         content_b64 = payload.get("content", "")
#         sha = payload.get("sha")
#         # content may include newlines - remove them before decoding
#         content_bytes = base64.b64decode(content_b64.encode())
#         return content_bytes, sha
#     elif resp.status_code == 404:
#         return None, None
#     else:
#         # raise or return None with logging
#         st.warning(f"GitHub GET returned {resp.status_code}: {resp.text}")
#         return None, None


# def github_put_file(repo: str, path: str, content_bytes: bytes, message: str, token: str, sha: str = None, branch: str = None):
#     """
#     Create or update a file in the repo. Returns response JSON.
#     """
#     if not token:
#         raise RuntimeError("GitHub token required to write to repo")
#     url = f"https://api.github.com/repos/{repo}/contents/{path}"
#     headers = {"Accept": "application/vnd.github+json", "Authorization": f"token {token}"}
#     content_b64 = base64.b64encode(content_bytes).decode()
#     data = {"message": message, "content": content_b64}
#     if sha:
#         data["sha"] = sha
#     if branch:
#         data["branch"] = branch
#     resp = requests.put(url, headers=headers, json=data)
#     if resp.status_code in (200, 201):
#         return resp.json()
#     else:
#         # bubble up useful info
#         raise RuntimeError(f"GitHub PUT failed ({resp.status_code}): {resp.text}")


# def load_entries_from_github(repo: str, path: str, token: str, branch: str = None):
#     """
#     Try to load CSV at repo/path and return a list of {"timestamp","action"} entries.
#     If file doesn't exist, returns [].
#     """
#     content_bytes, sha = github_get_file(repo, path, token, branch)
#     if content_bytes is None:
#         return []  # no file yet
#     try:
#         s = content_bytes.decode("utf-8")
#         df = pd.read_csv(io.StringIO(s), index_col=None)
#         # Expect columns 'timestamp' and 'action' (index column if present ignored)
#         # Normalize to list of dicts
#         entries = []
#         for _, row in df.iterrows():
#             # handle if CSV had an index column named 'No.' or similar
#             ts = row.get("timestamp") if "timestamp" in row else None
#             action = row.get("action") if "action" in row else None
#             if pd.isna(ts) or pd.isna(action):
#                 continue
#             entries.append({"timestamp": str(ts), "action": str(action)})
#         return entries
#     except Exception as e:
#         st.warning(f"Failed to parse CSV from GitHub: {e}")
#         return []


# def save_entries_to_github(entries: list, repo: str, path: str, token: str, message: str = "Update entries CSV", branch: str = None):
#     """
#     Save the provided entries list into the CSV at repo/path.
#     This will create or update the file using the Contents API.
#     """
#     if not token:
#         # Do not attempt to write if no token supplied
#         st.warning("No GitHub token configured; entries will not be persisted to repo.")
#         return
#     # Fetch existing file SHA to update if exists (optional)
#     try:
#         existing_bytes, existing_sha = github_get_file(repo, path, token, branch)
#         # Prepare dataframe
#         df = pd.DataFrame(entries)
#         # Ensure column order
#         if "timestamp" in df.columns and "action" in df.columns:
#             df = df[["timestamp", "action"]]
#         csv_buf = io.StringIO()
#         # Do not include pandas index in the CSV we write (but we could add it if desired)
#         df.to_csv(csv_buf, index=False)
#         csv_bytes = csv_buf.getvalue().encode("utf-8")
#         # Use commit message with timestamp for traceability
#         commit_msg = f"{message} at {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S %Z')}"
#         github_put_file(repo, path, csv_bytes, commit_msg, token, sha=existing_sha, branch=branch)
#     except Exception as e:
#         st.error(f"Failed to save entries to GitHub: {e}")


# # --- Helper functions -------------------------------------------------------
# def init_session():
#     """Initialize session state keys used by the app. Load from GitHub if token present."""
#     if "entries" not in st.session_state:
#         st.session_state.entries = []
#     if "is_sleeping" not in st.session_state:
#         st.session_state.is_sleeping = False

#     token = get_github_token()
#     if token:
#         try:
#             loaded = load_entries_from_github(GITHUB_REPO, GITHUB_PATH, token, branch=GITHUB_BRANCH)
#             if loaded:
#                 st.session_state.entries = loaded
#                 # infer sleeping from the last entry if any
#                 last = st.session_state.entries[-1]
#                 if last.get("action") in ("sleep", "sleeping"):
#                     st.session_state.is_sleeping = True
#         except Exception as e:
#             st.warning(f"Could not load entries from GitHub: {e}")


# def current_ist_timestamp_str():
#     """Return the current time formatted in IST as a string."""
#     return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S %Z")


# def add_entry(action_label: str):
#     """Record a new entry with current timestamp (IST) and action label and persist to GitHub (if configured)."""
#     ts = current_ist_timestamp_str()
#     st.session_state.entries.append({"timestamp": ts, "action": action_label})
#     # keep entries reasonably small in memory (optional)
#     if len(st.session_state.entries) > 1000:
#         st.session_state.entries = st.session_state.entries[-1000:]

#     # Persist to GitHub (best-effort). This runs synchronously here; for better UX run in background.
#     token = get_github_token()
#     if token:
#         try:
#             # provide a clear commit message
#             save_entries_to_github(
#                 st.session_state.entries,
#                 GITHUB_REPO,
#                 GITHUB_PATH,
#                 token,
#                 message=f"Streamlit: add {action_label}",
#                 branch=GITHUB_BRANCH,
#             )
#         except Exception as e:
#             st.warning(f"Could not persist to GitHub: {e}")


# # --- Initialize ----------------------------------------------------------------
# init_session()

# st.title("Baby Quick Actions")
# st.markdown(
#     "Use the quick action buttons to record events. The most recent 10 entries are shown below. You can download all entries as CSV (also persisted to the configured GitHub repo)."
# )

# # Layout: two main sections (quick actions | recent entries)
# left, right = st.columns([1, 1])

# with left:
#     st.header("Quick actions")
#     st.caption("Click a button to record the current timestamp (IST) and action.")

#     # Determine label for sleep button based on state
#     sleep_label = "Wake up" if st.session_state.is_sleeping else "Sleep"

#     # Buttons placed horizontally
#     b1, b2, b3 = st.columns(3)

#     with b1:
#         if st.button(sleep_label):
#             if st.session_state.is_sleeping:
#                 # Wake up flow
#                 add_entry("awake")
#                 st.session_state.is_sleeping = False
#                 st.success(f"Recorded: awake at {current_ist_timestamp_str()}")
#             else:
#                 # Go to sleep flow
#                 add_entry("sleep")
#                 st.session_state.is_sleeping = True
#                 st.success(f"Recorded: sleep at {current_ist_timestamp_str()}")

#     with b2:
#         if st.button("Diaper change"):
#             add_entry("diaper change")
#             st.success(f"Recorded: diaper change at {current_ist_timestamp_str()}")

#     with b3:
#         if st.button("Poop"):
#             add_entry("poop")
#             st.success(f"Recorded: poop at {current_ist_timestamp_str()}")

#     st.markdown("---")
#     st.markdown("Session controls")
#     sc1, sc2 = st.columns([1, 1])
#     with sc1:
#         if st.button("Clear recent entries"):
#             st.session_state.entries = []
#             st.session_state.is_sleeping = False
#             # Optionally persist cleared state
#             token = get_github_token()
#             if token:
#                 try:
#                     save_entries_to_github(st.session_state.entries, GITHUB_REPO, GITHUB_PATH, token, message="Clear all entries", branch=GITHUB_BRANCH)
#                 except Exception as e:
#                     st.warning(f"Could not persist clear to GitHub: {e}")
#             st.info("All entries cleared for this session (and repo if token configured).")
#     with sc2:
#         if st.button("Add sample entry (feed)"):
#             add_entry("feed")
#             st.success(f"Sample 'feed' entry added at {current_ist_timestamp_str()}.")


# with right:
#     st.header("Recent entries (latest 10)")
#     entries = list(st.session_state.entries)  # copy for safety
#     if not entries:
#         st.info("No entries yet. Use the quick action buttons to record events.")
#     else:
#         # Show the most recent 10 entries (newest first)
#         recent = entries[-10:][::-1]
#         df_recent = pd.DataFrame(recent)
#         # Ensure nice column order
#         df_recent = df_recent[["timestamp", "action"]]
#         # Make index visible and start at 1 for user friendliness
#         df_recent.index = range(1, len(df_recent) + 1)
#         df_recent.index.name = "No."
#         st.dataframe(df_recent, use_container_width=True)

#         # Download all entries as CSV (not just recent 10)
#         df_all = pd.DataFrame(entries)
#         if not df_all.empty:
#             df_all = df_all[["timestamp", "action"]]
#             # add 1-based index for CSV
#             df_all.index = range(1, len(df_all) + 1)
#             df_all.index.name = "No."
#             csv_all = df_all.to_csv(index=True).encode("utf-8")
#             st.download_button(
#                 "Download all entries as CSV",
#                 data=csv_all,
#                 file_name="all_entries.csv",
#                 mime="text/csv",
#             )

# # Footer note
# st.markdown(
#     """
#     Notes:
#     - The Sleep button toggles to 'Wake up' automatically when the session state indicates the last recorded action was 'sleep'.
#     - All timestamps are recorded in IST (India Standard Time).
#     - Recent entries panel shows the latest 10 actions and includes a visible index column starting at 1.
#     - The download button provides a CSV containing ALL session entries (with index).
#     - If you configured a GitHub token (GITHUB_TOKEN in Streamlit secrets or env var), entries will be loaded from and saved to the CSV in the configured repo/path.
#     - Writing to the repo uses your token and the GitHub Contents API (commits are created for each save).
#     - For production usage with many writes or multiple users, prefer a proper backend (database, S3/GCS, or Sheets) to avoid race conditions and frequent repo commits.
#     """
# )
