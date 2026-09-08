from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import json

root = Path(__file__).resolve().parents[1] / "data" / "validation"
soup = BeautifulSoup((root / "mega_jundiai.html").read_text(encoding="utf-8"), "lxml")
links = []
for anchor in soup.select("a[href]"):
    if "J127385" in anchor.get("href", "").upper() or "J128502" in anchor.get("href", "").upper() or "J128529" in anchor.get("href", "").upper():
        href = anchor["href"]
        if href not in links:
            links.append(href)
            print(str(anchor.parent)[:1800])
options = Options()
options.add_argument("--headless=new")
with webdriver.Chrome(options=options) as browser:
    browser.set_page_load_timeout(45)
    for index, url in enumerate(links):
        if url.startswith("/"):
            url = "https://www.megaleiloes.com.br" + url
        browser.get(url)
        (root / f"mega_detail_{index}.html").write_text(browser.page_source, encoding="utf-8")
        print(json.dumps({"file": index, "url": url, "text": browser.find_element("tag name", "body").text[:13500]}, ensure_ascii=True))
