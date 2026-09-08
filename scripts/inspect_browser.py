"""Read public pages using an ordinary headless browser; stop on a challenge."""
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import json

root = Path(__file__).resolve().parents[1] / "data" / "validation"
root.mkdir(parents=True, exist_ok=True)
options = Options()
options.add_argument("--headless=new")
options.add_argument("--window-size=1440,1000")
with webdriver.Chrome(options=options) as browser:
    browser.set_page_load_timeout(45)
    for name, url in [
        ("mega_jundiai", "https://www.megaleiloes.com.br/imoveis/sp/jundiai"),
        ("zuk_jundiai", "https://www.portalzuk.com.br/leilao-de-imoveis/c/todos-imoveis/sp/interior/jundiai"),
    ]:
        try:
            browser.get(url)
            text = browser.find_element("tag name", "body").text
            (root / f"{name}.html").write_text(browser.page_source, encoding="utf-8")
            print(json.dumps({"name": name, "url": browser.current_url, "text": text[:1800]}, ensure_ascii=True))
        except Exception as exc:
            print(name, type(exc).__name__)
