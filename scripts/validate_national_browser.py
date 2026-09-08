import sys
import json
from pathlib import Path
from urllib.parse import urlencode
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from leilao_app.services.catalog import load_catalog, filter_properties
items=load_catalog()
options=webdriver.ChromeOptions()
options.add_argument('--headless=new')
report=[]
with webdriver.Chrome(options=options) as browser:
    for uf, city in [('AM','Manaus'),('BA','Salvador'),('DF','Brasília'),('RJ','Rio de Janeiro'),('RS','Porto Alegre')]:
        expected=len(filter_properties(items,{'state':uf,'city':city}))
        assert expected>0,(uf,city)
        browser.get('http://localhost:8512/?'+urlencode({'state':uf,'city':city,'busca':1}))
        WebDriverWait(browser,90).until(lambda d: f'{expected} imóveis encontrados' in d.find_element(By.TAG_NAME,'body').text)
        assert not browser.find_elements(By.CSS_SELECTOR,"[data-testid='stException']")
        cards=browser.find_elements(By.CSS_SELECTOR,'.pl-card')
        assert cards
        assert all('/ '+uf in card.text for card in cards)
        report.append({'state':uf,'city':city,'results':expected,'browser':'PASS'})
        print(report[-1],flush=True)
    browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',{'width':375,'height':900,'deviceScaleFactor':1,'mobile':True})
    assert browser.execute_script('return document.documentElement.scrollWidth <= window.innerWidth')
Path('data/validation/national_browser.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
