from flask import Flask, render_template, redirect, url_for, flash, request
from datetime import datetime, timedelta
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import json
import os
from disaster_scrape import run_scraper

app = Flask(__name__)

LOCAL_JSON_PATH = "static/data/summaries_by_province.json"
TARGET_FILENAME = "summaries_by_province.json"

def sync_from_cloud():
    try:
        gauth = GoogleAuth()
        
        gauth.LoadCredentialsFile("credentials.txt") 
        
        if gauth.credentials is None:
            gauth.LocalWebserverAuth()
        elif gauth.access_token_expired:
            gauth.Refresh()
        else:
            gauth.Authorize()
        
        drive = GoogleDrive(gauth)
        
        query = f"title='{TARGET_FILENAME}' and trashed=false"
        file_list = drive.ListFile({'q': query}).GetList()
        
        if file_list:
            target_file = file_list[0]
            
            target_file.GetContentFile(LOCAL_JSON_PATH)
        else:
            
    except Exception as e:

@app.route("/")
def home():
    sync_from_cloud()
    
    data = []
    if os.path.exists(LOCAL_JSON_PATH):
        try:
            with open(LOCAL_JSON_PATH, 'r', encoding='utf-8') as f:
                json_content = json.load(f)
                data = json_content.get("all_data", [])
        except Exception as e:
    
    return render_template("index.html", articles=data)

@app.route("/run-ingestion")
def run_ingestion():
    try:
        days = request.args.get('days', default=7, type=int)
    
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        run_scraper(start_date=start_date, end_date=end_date)
        
        return render_template("success.html", days=days)
        
    except Exception as e:
        return f"Error running scraper: {e}"

if __name__ == "__main__":
    os.makedirs("static/data", exist_ok=True)
    app.run(debug=True)