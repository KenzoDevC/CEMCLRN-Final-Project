import requests
import time
import random
import csv
import os
from curl_cffi import requests
from bs4 import BeautifulSoup
import re


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

# def get_article_text(url):
#     chrome_options = Options()
    
#     chrome_options.add_argument("--headless=new") 
    
#     chrome_options.add_argument('--ignore-certificate-errors')
#     chrome_options.add_argument('--allow-insecure-localhost')

#     user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
#     chrome_options.add_argument(f'user-agent={user_agent}')

#     chrome_options.add_argument("--log-level=3")

#     chrome_options.page_load_strategy = 'eager'

#     prefs = {"profile.managed_default_content_settings.images": 2}
#     chrome_options.add_experimental_option("prefs", prefs)

#     try:
#         service = ChromeService(ChromeDriverManager().install())
#         driver = webdriver.Chrome(service=service, options=chrome_options)

#     except Exception as e:
#         print(f"Webdriver Error: {e}")
#         return "Error"

#     try:
#         start = time.time()
#         driver.get(url)

#         try:
#             wait = WebDriverWait(driver, 10) # Max wait 10s
#             container = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "imp-article-0")))
#         except Exception:
#             print(f"Error: Element not found on {url}")
#             return "Error"

#         article_text = ""
#         paragraphs = container.find_elements(By.TAG_NAME, 'p')

#         for p_element in paragraphs:
#             text = p_element.text

#             try:
#                 text = text.encode('iso-8859-1').decode('utf-8')
#             except (UnicodeEncodeError, UnicodeDecodeError):
#                 pass

#             article_text += text.strip() + " "

#         end = time.time()

#         length = end-start

#         print(f"Took {length} seconds to scrape")

#         article_text = article_text.replace("ADVERTISEMENT", "")

#         return article_text

#     except Exception as e:
#         print(f"Article Error: {e}")
#         return "Error"
#     finally:
#         if 'driver' in locals() and driver:
#             driver.quit()

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

def run_scraper():
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

                current_offset += returned_count
                time.sleep(1)

            except Exception as e:
                print(f"Syntax Error: {e}")
                break

            end = time.time()

            length = end - start

            print(f"took {length} seconds to get data")
    print("\n done.")
    
if __name__ == "__main__":
    run_scraper()