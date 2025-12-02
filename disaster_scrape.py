import requests
import time
import random
import csv
import os
from curl_cffi import requests
from bs4 import BeautifulSoup
import re
from pydrive.auth import GoogleAuth	# pip install pydrive
from pydrive.drive import GoogleDrive
from datetime import datetime, timedelta
from dateutil import parser

LIMIT = 500
MAX_LOOPS = 1
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, "disaster_articless.csv")
URL_TEMPLATE = "https://od2-content-api.abs-cbn.com/prod/latest?sectionId=nation&brand=OD&partner=imp-01&limit={}&offset={}"


TARGET_TAGS = {
    "earthquake", 
    "fire", 
    "typhoon", 
    "super typhoon",
    "bagyo",
    "flooding", 
    "volcanic eruption", 
    "tsunami risk",
    "disaster",
    "calamity",
    "tropical storm",
    "typhoons",
    "flood"
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://news.abs-cbn.com/"
}


def is_disaster(article):
    raw_tags_string = article.get("tags")
    if not raw_tags_string:
        return False, None

    tags_lower = raw_tags_string.lower()

    for target in TARGET_TAGS:
        if target in tags_lower:
            return True, target

    return False, None

def clean_text(html_string):
    if not html_string:
        return ""

    soup = BeautifulSoup(html_string, 'html.parser')

    for element in soup.find_all(class_=['fr-img-caption', 'fr-img-wrap', 'img']):
        element.decompose()
    
    for link in soup.find_all('a'):
        link.replace_with(link.get_text())

    for element in soup.find_all(['iframe', 'span', 'strong'], class_=['fr-video', 'fr-deletable', 'fr-fvc', 'fr-dvb', 'fr-draggable']):
        element.decompose()
        
    for element in soup.find_all(['script', 'style', 'noscript', 'br']):
        element.decompose()

    for p in soup.find_all('p'):
        if not p.get_text(strip=True):
            p.decompose()

    raw_text = soup.get_text(separator='\n', strip=True)

    cleaned_text = re.sub(r'(\n{3,})', '\n\n', raw_text)
    
    cleaned_text = cleaned_text.strip()
    
    cleaned_text = re.sub(r'[ \t]+', ' ', cleaned_text)

    return cleaned_text

def get_article_text(url, headers):
    target_url = "https://od2-content-api.abs-cbn.com/prod/pageinfo?url=" + url
    response = requests.get(target_url, headers=headers)

    if response.status_code != 200:
        return(f"Error: {response.status_code}")
    data = response.json()
    article_data = data["data"]["body_html"]

    cleaned = clean_text(article_data)

    return cleaned

def get_or_create_shared_folder(drive, folder_name="DisasterArticles"):
    query = f"title='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    file_list = drive.ListFile({'q': query}).GetList()
    
    if file_list:
        folder = file_list[0]  # get first folder
     
    share_link = folder['alternateLink']
    print(f"Shareable folder link: {share_link}")
    
    return folder['id'], share_link


def date_in_range(article_date_str, start_date, end_date):
    try:
        article_dt = parser.parse(article_date_str).date()
    except:
        return False
    return start_date <= article_dt <= end_date


def upload_to_drive(file_path):
    gauth = GoogleAuth()
    gauth.LoadCredentialsFile("credentials.txt")

    if gauth.credentials is None:
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        gauth.Refresh()
    else:
        gauth.Authorize()

    gauth.SaveCredentialsFile("credentials.txt")
    drive = GoogleDrive(gauth)
    folder_id, share_link = get_or_create_shared_folder(drive)

    file = drive.CreateFile({
        'title': os.path.basename(file_path),
        'parents': [{'id': folder_id}]
    })
    file.SetContentFile(file_path)
    file.Upload()
    print(f"Uploaded {file_path} to {share_link}")


def run_scraper(start_date=None, end_date=None):
    # Set default date range to past 7 days if not provided
    if start_date is None or end_date is None:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)

    file_exists = os.path.isfile(OUTPUT_FILE)
    with open(OUTPUT_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Date", "Headline", "Keyword", "Link", "Tags", "Abstract", "Article"])

        print(f"Scraping articles from {start_date} to {end_date}")

    file_exists = os.path.isfile(OUTPUT_FILE)
    with open(OUTPUT_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Date", "Headline", "Keyword", "Link", "Tags", "Abstract", "Article"])

        print("Scraping with Limit = {LIMIT} per request")

        for i in range(MAX_LOOPS):
            start = time.time()
            current_offset = i * LIMIT
            target_url = URL_TEMPLATE.format(LIMIT, current_offset)

            print(f"Fetching: {target_url}")

            try:
                print(f"{target_url}")
                response = requests.get(target_url, headers=headers)

                if response.status_code != 200:
                    print(f"Error: {response.status_code}")
                    break

                data = response.json()

                articles = data.get("listItem", [])

                if not articles:
                    print("No more articles found.")
                    break

                returned_count = len(articles)
                print(f"Returned {returned_count} articles")

                matches = 0
                for item in articles:
                    match, kw = is_disaster(item)
                    if match:
                        # check date
                        article_date = item.get("createdDateFull")

                        if start_date and end_date:
                            if not date_in_range(article_date, start_date, end_date):
                                continue   # skip

                        # only continues here if date is valid
                        matches += 1
                        writer.writerow([
                            item.get("createdDateFull"),
                            item.get("title"),
                            kw,
                            f"https://news.abs-cbn.com/{item.get('slugline_url')}",
                            item.get("tags"),
                            item.get("abstract"),
                            get_article_text(f"{item.get('slugline_url')}", headers)
                        ])
                current_offset += returned_count
                time.sleep(1)

            except Exception as e:
                print(f"Syntax Error: {e}")
                break

            end = time.time()

            length = end - start

            print(f"took {length} seconds to get data")
    print("\n done.")
    try:
        import pandas as pd
        df = pd.read_csv(OUTPUT_FILE)

        # Remove duplicates based on Link
        df = df.drop_duplicates(subset=["Link"], keep="first")

        df.to_csv(OUTPUT_FILE, index=False)

        print("Removed duplicates based on 'Link'.")
    except Exception as e:
        print(f"Duplicate cleanup error: {e}")

    return OUTPUT_FILE
    #upload_to_drive(OUTPUT_FILE)
    
if __name__ == "__main__":
    run_scraper()
