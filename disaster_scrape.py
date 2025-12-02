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

LIMIT = 100
MAX_LOOPS = 1
OUTPUT_FILE = "disaster_articless.csv"
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
    
    article_tags = [t.strip().lower() for t in raw_tags_string.split(',')]

    for target in TARGET_TAGS:
        if target in article_tags:
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

def get_gdrive_folder(drive, folder_name="DisasterArticles"):
    query = f"title='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    file_list = drive.ListFile({'q': query}).GetList()
    
    if file_list:
        folder = file_list[0]
     
    share_link = folder['alternateLink']
    print(f"Shareable folder link: {share_link}")
    
    return folder['id'], share_link

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
    folder_id, share_link = get_gdrive_folder(drive)

    file = drive.CreateFile({
        'title': os.path.basename(file_path),
        'parents': [{'id': folder_id}]
    })
    file.SetContentFile(file_path)
    file.Upload()
    print(f"Uploaded {file_path} to {share_link}")

    return drive, folder_id

def poll_result(drive, folder_id, input_file, processed_prefix="processed_", timeout=3600, interval=5):
    start_time = time.time()
    base_name = os.path.basename(input_file)
    processed_name = processed_prefix + base_name
    while time.time() - start_time < timeout:
        query = f"'{folder_id}' in parents and title = '{processed_name}' and trashed=false"
        file_list = drive.ListFile({'q': query}).GetList()
        if file_list:
            processed_file = file_list[0]
            processed_file.GetContentFile(processed_name)
            print(f"Downloaded processed file: {processed_name}")
            return True
        print(f"Waiting for {processed_name}...")
        time.sleep(interval)
    print("Timeout waiting for processed file.")
    return False

def run_scraper():
    file_exists = os.path.isfile(OUTPUT_FILE)
    existing_links = set()

    if file_exists:
        with open(OUTPUT_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                if row and len(row) > 3:
                    existing_links.add(row[3])  # Link is at index 3

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
                        link = f"https://news.abs-cbn.com/{item.get('slugline_url')}"
                        if link in existing_links:
                            print(f"Skipping duplicate: {link}")
                            continue
                        matches +=1
                        writer.writerow([
                            item.get("createdDateFull"),
                            item.get("title"),
                            kw,
                            f"https://news.abs-cbn.com/{item.get('slugline_url')}",
                            item.get("tags"),
                            item.get("abstract"),
                            get_article_text(f"{item.get('slugline_url')}", headers)
                        ])
                        existing_links.add(link)

                current_offset += returned_count
                time.sleep(1)

            except Exception as e:
                print(f"Syntax Error: {e}")
                break

            end = time.time()

            length = end - start

            print(f"took {length} seconds to get data")
    print("\n done.")

    drive, folder_id = upload_to_drive(OUTPUT_FILE)
    poll_result(drive, folder_id, OUTPUT_FILE)
    
if __name__ == "__main__":
    run_scraper()
