import os
import openpyxl
from datetime import datetime, timedelta, timezone
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# Path to network folder
EXCEL_FILE = r"\\192.168.0.200\network folders\web scrapper\scraped_data.xlsx"
WEATHER_URL = "https://weather.com/en-PH/weather/hourbyhour/l/efcd40fe1793cc6be2a4dcd36299b56d4be59a540df869069f976bc88b0ff942"

# Get current Philippine time
ph_tz = timezone(timedelta(hours=8))
now = datetime.now(ph_tz)
next_day_8am = (now + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)


def scrape_precipitation():
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(WEATHER_URL)

    precipitation_data = []
    time_elements = driver.find_elements(By.CSS_SELECTOR, "[data-testid=hourly-time]")
    precipitation_elements = driver.find_elements(By.CSS_SELECTOR, "[data-testid=PercentageValue]")

    for time_el, precip_el in zip(time_elements, precipitation_elements):
        time_text = time_el.text.strip()
        precip_value = precip_el.text.replace("%", "").strip()

        try:
            record_time = datetime.strptime(time_text, "%I %p").replace(year=now.year, month=now.month, day=now.day,
                                                                        tzinfo=ph_tz)
            if record_time < now:
                record_time += timedelta(days=1)
        except ValueError:
            continue

        if now <= record_time <= next_day_8am and precip_value.isdigit():
            precipitation_data.append((record_time.isoformat(), int(precip_value)))

    driver.quit()
    return precipitation_data


def save_to_excel(data):
    wb = openpyxl.Workbook() if not os.path.exists(EXCEL_FILE) else openpyxl.load_workbook(EXCEL_FILE)
    ws = wb.active

    ws.append(["Timestamp", "Precipitation Data"])
    for timestamp, value in data:
        ws.append([timestamp, value])

    wb.save(EXCEL_FILE)
    print(f"📂 Scraped data saved to {EXCEL_FILE}")


if __name__ == "__main__":
    precipitation_data = scrape_precipitation()
    if precipitation_data:
        save_to_excel(precipitation_data)
    else:
        print("⚠️ No precipitation data found.")