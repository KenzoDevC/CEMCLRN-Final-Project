# app.py
import os
import shutil
import logging
from datetime import datetime, timedelta, time
from flask import Flask, render_template
from disaster_scrape import run_scraper     # must return path to produced CSV
from cloud_pipeline import run_cloud_model  # function that reads csv and writes static/data/summaries_by_province.json

# Optional: if you publish scheduled CSVs to GitHub raw, you can enable this:
USE_GITHUB_RAW_FALLBACK = False
GITHUB_RAW_CSV_URL_TEMPLATE = "https://raw.githubusercontent.com/{owner}/{repo}/{branch}/data/{fname}"
# example: owner="you", repo="disaster-repo", branch="main", fname e.g. "disaster_20251126_12.csv"

# Where we store local scheduled CSVs and cloud outputs
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "static", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Where run_scraper writes by default (your scraper may write OUTPUT_FILE; we will rename/copy)
# If run_scraper returns its path, we use it directly.
SCRAPER_OUTPUT_DEFAULT = os.path.join(BASE_DIR, "disaster_articless.csv")

# Flask app
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# -------- Helper functions --------
def get_current_slot(now=None):
    """
    Return the datetime representing the most recent scheduled slot (0,6,12,18 hrs)
    For example, if now is 2025-12-02 14:23 -> returns 2025-12-02 12:00
    """
    now = now or datetime.now()
    hour = now.hour
    # slots: 0,6,12,18
    slot_hours = [0, 6, 12, 18]
    slot_hour = max([h for h in slot_hours if h <= hour])
    slot_dt = datetime(year=now.year, month=now.month, day=now.day, hour=slot_hour)
    return slot_dt

def slot_filename(slot_dt):
    """
    Deterministic filename for a slot CSV, stored in DATA_DIR
    Format: disaster_YYYYmmdd_HH.csv  (HH is 00,06,12,18)
    """
    fname = f"disaster_{slot_dt.strftime('%Y%m%d_%H')}.csv"
    return os.path.join(DATA_DIR, fname)

def file_is_valid_for_slot(filepath, slot_dt):
    """
    Check if filepath exists and its mtime is >= slot_dt (i.e. generated for that slot)
    """
    if not os.path.exists(filepath):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
    # allow some small clock skew: require mtime >= slot_dt - 5 minutes
    if mtime + timedelta(seconds=1) >= slot_dt - timedelta(minutes=5):
        return True
    return False

def try_fetch_csv_from_github(owner, repo, branch, local_target_path, slot_dt):
    """
    Optional helper to download a scheduled CSV published in GitHub raw.
    Returns True if downloaded and valid.
    """
    import requests
    fname = os.path.basename(local_target_path)
    url = GITHUB_RAW_CSV_URL_TEMPLATE.format(owner=owner, repo=repo, branch=branch, fname=fname)
    logging.info("Attempting fetch from GitHub raw: %s", url)
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200 and r.content:
            with open(local_target_path, "wb") as fh:
                fh.write(r.content)
            return file_is_valid_for_slot(local_target_path, slot_dt)
        else:
            logging.info("GitHub raw not available (status %s)", r.status_code)
            return False
    except Exception as e:
        logging.exception("Error fetching GitHub raw: %s", e)
        return False

def ensure_slot_csv(slot_dt, allow_run_scraper=True):
    """
    Ensure CSV for slot exists in DATA_DIR. If present and valid, return its path.
    Otherwise, if allow_run_scraper True, run run_scraper() now produce CSV and copy to slot file.
    Returns path to CSV for slot, or None if not available.
    """
    target = slot_filename(slot_dt)
    logging.info("Ensuring CSV for slot %s -> %s", slot_dt, target)

    # If already present locally and valid -> use it
    if file_is_valid_for_slot(target, slot_dt):
        logging.info("Found existing CSV for slot: %s", target)
        return target

    # Optional: try fetching from GitHub raw if configured (USE_GITHUB_RAW_FALLBACK must be True)
    if USE_GITHUB_RAW_FALLBACK:
        # set these variables to your repo details if you want fallback
        owner = "YOUR_GITHUB_USER"
        repo = "YOUR_REPO"
        branch = "main"
        if try_fetch_csv_from_github(owner, repo, branch, target, slot_dt):
            logging.info("Fetched slot CSV from GitHub raw.")
            return target

    # If we're not allowed to run scraper now, return None
    if not allow_run_scraper:
        logging.info("Not allowed to run scraper now; returning None.")
        return None

    # Otherwise run scraper now and produce a CSV
    logging.info("Running scraper now to produce CSV for slot.")
    produced = run_scraper(start_date=slot_dt.date(), end_date=(slot_dt + timedelta(hours=6)).date())
    # run_scraper is expected to return a file path (probably SCRAPER_OUTPUT_DEFAULT)
    produced_path = produced if produced else SCRAPER_OUTPUT_DEFAULT
    if not os.path.exists(produced_path):
        logging.error("Scraper did not produce expected file: %s", produced_path)
        return None
    # Move/copy produced to target slot filename
    try:
        shutil.copy2(produced_path, target)
        logging.info("Copied produced CSV %s -> %s", produced_path, target)
        return target
    except Exception as e:
        logging.exception("Failed to copy produced CSV to slot target: %s", e)
        return None

# -------- Flask routes --------
@app.route("/", methods=["GET"])
def home():
    """
    On user access:
    - compute current slot (most recent scheduled slot)
    - if slot CSV exists (mtime >= slot), use it (DO NOT re-run cloud model)
    - otherwise: run scraper now and run cloud model (summarize), then serve updated page
    """
    now = datetime.now()
    slot_dt = get_current_slot(now)
    # determine whether we should allow scraping: we allow it if no CSV exists for slot
    csv_path = ensure_slot_csv(slot_dt, allow_run_scraper=False)
    if csv_path:
        # CSV exists for slot -> use it, DO NOT run cloud model now
        logging.info("Slot CSV exists. Using existing CSV: %s", csv_path)
        # Ensure the cloud summary JSON also exists; if not, produce it
        summary_json = os.path.join(DATA_DIR, "summaries_by_province.json")
        if not os.path.exists(summary_json) or not file_is_valid_for_slot(summary_json, slot_dt):
            # Produce summaries using the CSV (but do not re-scrape)
            logging.info("Summary JSON missing or stale. Running cloud model now using existing CSV.")
            #run_cloud_model(csv_path)
        return render_template("index.html")
    else:
        # No CSV for slot yet. We must run scraper now and then run cloud model.
        logging.info("No CSV for slot found. Running scraper now.")
        csv_path = ensure_slot_csv(slot_dt, allow_run_scraper=True)
        if not csv_path:
            logging.error("Failed to produce CSV for slot.")
            return render_template("index.html", error="Failed to fetch or produce CSV")
        # Run cloud model to generate summaries JSON
        logging.info("Running cloud model to summarize CSV: %s", csv_path)
        #run_cloud_model(csv_path)
        return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
