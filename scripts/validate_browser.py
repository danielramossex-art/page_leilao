"""Real-browser smoke tests against the running local Streamlit app."""
from pathlib import Path
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

root = Path(__file__).resolve().parents[1] / "data" / "validation"
root.mkdir(parents=True, exist_ok=True)
options = webdriver.ChromeOptions()
options.add_argument("--headless=new")
options.add_argument("--window-size=1440,1100")
report = {}
with webdriver.Chrome(options=options) as browser:
    wait = WebDriverWait(browser, 30)
    def text():
        return browser.find_element(By.TAG_NAME, "body").text
    def until_text(value):
        wait.until(lambda _: value in text())
    def button(label):
        node = wait.until(EC.element_to_be_clickable((By.XPATH, f"//button[normalize-space()='{label}']")))
        browser.execute_script("arguments[0].scrollIntoView({block:'center'});", node)
        node.click()
    def choose(label, value):
        box = wait.until(EC.element_to_be_clickable((By.XPATH, f"//div[@data-testid='stSelectbox'][.//label[normalize-space()='{label}']]//div[@data-baseweb='select']")))
        box.click()
        wait.until(EC.element_to_be_clickable((By.XPATH, f"//*[@role='option' and normalize-space()='{value}']"))).click()
    def loaded_photos():
        count = 0
        for frame in browser.find_elements(By.CSS_SELECTOR, "iframe[srcdoc]"):
            browser.switch_to.frame(frame)
            try:
                count += browser.execute_script("return [...document.images].filter(i=>i.complete && i.naturalWidth>0).length")
            finally:
                browser.switch_to.default_content()
        return count
    browser.get("http://localhost:8512")
    until_text("Encontre oportunidades em imóveis")
    assert not browser.find_elements(By.CSS_SELECTOR, "[data-testid='stException']"), text()
    browser.save_screenshot(str(root / "home_desktop.png"))
    choose("Estado", "SP")
    choose("Cidade", "Jundiaí")
    button("Buscar imóveis")
    until_text("5 imóveis encontrados")
    wait.until(lambda _: len(browser.find_elements(By.CSS_SELECTOR, ".pl-card")) == 5)
    wait.until(lambda _: loaded_photos() == 5)
    report["search"] = {"results": 5, "city": "Jundiaí/SP", "loaded_photos": loaded_photos()}
    links = [node.get_attribute("href") for node in browser.find_elements(By.CSS_SELECTOR, ".pl-card .pl-link")]
    browser.execute_script("window.scrollTo(0,0)")
    browser.save_screenshot(str(root / "results_desktop.png"))
    button("Mais filtros")
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "[role='dialog']")))
    assert "Valor mínimo" in text() and "Aceita financiamento" in text()
    button("Aplicar filtros")
    wait.until(lambda _: not browser.find_elements(By.CSS_SELECTOR, "[role='dialog']"))
    report["advanced_filters"] = "PASS"
    details = []
    for link in links[:3]:
        browser.get(link)
        until_text("Análise Seach page Leilão")
        assert not browser.find_elements(By.CSS_SELECTOR, "[data-testid='stException']"), text()
        wait.until(lambda _: loaded_photos() == 1)
        assert "Valor de avaliação informado pela fonte" in text()
        assert "0,0% abaixo da avaliação" in text()
        official = next(a.get_attribute("href") for a in browser.find_elements(By.TAG_NAME, "a") if a.text == "Ver na fonte oficial")
        expected = {"j127385": "R$ 596.025,74", "j128502": "R$ 648.396,00", "j128529": "R$ 538.051,41"}
        assert any(code in official and price in text() for code, price in expected.items())
        details.append({"local": browser.current_url, "official": official, "photo_loaded": True, "price_match": True})
    browser.save_screenshot(str(root / "detail_desktop.png"))
    report["details"] = details
    browser.switch_to.frame(browser.find_element(By.CSS_SELECTOR, "iframe[srcdoc]"))
    browser.execute_script("document.querySelector('img').src='data:image/png;base64,invalid'")
    wait.until(lambda _: browser.execute_script("return document.querySelector('img').hidden && document.getElementById('fallback').textContent==='Imagem não disponível'"))
    browser.switch_to.default_content()
    browser.save_screenshot(str(root / "image_placeholder.png"))
    report["broken_image_placeholder"] = "PASS"
    button("♡ Favoritar")
    until_text("★ Favorito")
    browser.refresh()
    until_text("★ Favorito")
    button("★ Favorito")
    until_text("♡ Favoritar")
    report["favorites_persist"] = "PASS"
    browser.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {"width": 375, "height": 900, "deviceScaleFactor": 1, "mobile": True})
    assert browser.execute_script("return window.innerWidth") == 375
    browser.refresh()
    until_text("Análise Seach page Leilão")
    browser.save_screenshot(str(root / "detail_mobile.png"))
    assert not browser.execute_script("return document.documentElement.scrollWidth>window.innerWidth"), "Horizontal overflow on detail"
    browser.get("http://localhost:8512/?state=SP&city=Jundia%C3%AD&busca=1")
    until_text("5 imóveis encontrados")
    browser.save_screenshot(str(root / "results_mobile.png"))
    frame = browser.find_element(By.CSS_SELECTOR, "iframe[srcdoc]")
    browser.execute_script("arguments[0].scrollIntoView({block:'start'});", frame)
    browser.save_screenshot(str(root / "card_mobile.png"))
    assert not browser.execute_script("return document.documentElement.scrollWidth>window.innerWidth"), "Horizontal overflow on results"
    button("Mais filtros")
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "[role='dialog']")))
    browser.save_screenshot(str(root / "filters_mobile.png"))
    button("Aplicar filtros")
    report["mobile_375"] = "PASS"
    browser.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {"width": 812, "height": 375, "deviceScaleFactor": 1, "mobile": True})
    browser.refresh()
    until_text("5 imóveis encontrados")
    assert not browser.execute_script("return document.documentElement.scrollWidth>window.innerWidth")
    report["landscape"] = "PASS"
    browser.get("http://localhost:8512/?state=SP&city=Jundia%C3%AD&max_price=1&busca=1")
    until_text("0 imóveis encontrados")
    report["empty_results"] = "PASS"
    assert not browser.find_elements(By.CSS_SELECTOR, "[data-testid='stException']"), text()
(root / "browser_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=True, indent=2))
