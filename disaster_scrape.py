import requests
import time
import csv
import os
import re


LIMIT = 100
MAX_LOOPS = 5
OUTPUT_FILE = "disaster_articles.csv"
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

def run_scraper():
    file_exists = os.path.isfile(OUTPUT_FILE)
    with open(OUTPUT_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Date", "Headline", "Keyword", "Link", "Tags"])

        print("Scraping with Limit = {LIMIt} per request")

        for i in range(MAX_LOOPS):
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
                        matches +=1
                        print(f"Found {item['title'][:40]}")
                        writer.writerow([
                            item.get("createdDateFull"),
                            item.get("title"),
                            kw,
                            f"https://news.abs-cbn.com/{item.get('slugline_url')}",
                            item.get("tags")
                        ])

                current_offset += returned_count

                time.sleep(1)

            except Exception as e:
                print(f"Syntax Error: {e}")
                break
    print("\n done.")

if __name__ == "__main__":
    run_scraper()