import requests
import time
import csv
import os
import re


LIMIT = 100
MAX_LOOPS = 10
tags = []
URL_TEMPLATE = "https://od2-content-api.abs-cbn.com/prod/latest?sectionId=nation&brand=OD&partner=imp-01&limit={}&offset={}"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://news.abs-cbn.com/"
}

def run_scraper():
        for i in range(MAX_LOOPS):
            current_offset = i * LIMIT
            target_url = URL_TEMPLATE.format(LIMIT, current_offset)

            print(f"Fetching: {target_url}")

            try:
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

                for item in articles:
                    raw_tags_string = item.get("tags")
                    article_tags = [t.strip().lower() for t in raw_tags_string.split(',')]

                    for tag in article_tags:
                         if tag not in tags:
                              tags.append(tag)

                current_offset += returned_count

                time.sleep(3)

            except Exception as e:
                print(f"Syntax Error: {e}")
                break
        for tag in tags:
            print(f"{tag} \n")
    

if __name__ == "__main__":
    run_scraper()