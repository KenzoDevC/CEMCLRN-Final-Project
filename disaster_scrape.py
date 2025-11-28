import requests
import time
import random
import csv
import os
from curl_cffi import requests
from bs4 import BeautifulSoup


LIMIT = 100
MAX_LOOPS = 1
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

def get_article_text(url):
    try:
        sleep_time = random.uniform(3, 7)
        print(f"      ... sleeping {sleep_time:.1f}s ...")
        time.sleep(sleep_time)

        response = requests.get(url, impersonate="chrome107", headers=headers)

        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            return "Error"

        soup = BeautifulSoup(response.content, 'html.parser')

        article_text = ""

        containers = soup.find_all(class_ = "MuiBox-root css-1bmy43m")

        for container in containers:
            paragraph_text = container.find('p')
            if paragraph_text:
                article_text += paragraph_text.get_text().strip() + " "
                print(article_text)

        return article_text
    except Exception as e:
        print(f"Article Error: {e}")
        return "Error"
        

def run_scraper():
    file_exists = os.path.isfile(OUTPUT_FILE)
    with open(OUTPUT_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Date", "Headline", "Keyword", "Link", "Tags", "Abstract", "Article"])

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
                        writer.writerow([
                            item.get("createdDateFull"),
                            item.get("title"),
                            kw,
                            f"https://news.abs-cbn.com/{item.get('slugline_url')}",
                            item.get("tags"),
                            item.get("abstract"),
                            get_article_text(f"https://news.abs-cbn.com/{item.get('slugline_url')}")
                        ])

                current_offset += returned_count

                time.sleep(1)

            except Exception as e:
                print(f"Syntax Error: {e}")
                break
    print("\n done.")
    


    
if __name__ == "__main__":
    run_scraper()