import requests
from bs4 import BeautifulSoup
from time import sleep
from datetime import datetime
import pandas as pd
import gspread
import os
import logging
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import random
import undetected_chromedriver as uc

#path to the file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
path_to_creds = os.path.join(BASE_DIR, 'creds.json')

#configurate google sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(path_to_creds, scope)
client = gspread.authorize(creds)
planner = client.open('Planner properties').sheet1

#headers for avoid anti-bot
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0"
}

config = uc.ChromeOptions()

#configurate logging
logging.basicConfig(
    level= logging.INFO,
    format= '%(asctime)s - [%(levelname)s] - %(message)s',
    handlers= [
        logging.FileHandler('scrap_properties.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logging.info('all configurated, starting scrap.')

class Scraper:
    def __init__(self):
        self.datas = []
        self.driver = uc.Chrome(options=config)
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    def take_datas(self):
            try:
                #loop for to extract properties
                for i in range(1, 100):
                    logging.info(f'extracting from the {i} page')
                    sleep(random.uniform(6, 10))
                    if i == 1:
                        url = 'https://www.pararius.com/apartments/amsterdam'
                    else:
                        url = f'https://www.pararius.com/apartments/amsterdam/page-{i}'
                    #requesting the html
                    self.driver.delete_all_cookies()
                    self.driver.get(url)
                    sleep(5)
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')

                    #defining the 'boxes' that contains the data
                    properties = soup.find_all('section', class_='listing-search-item')

                    if not properties:
                        logging.info('end of the pages.')
                        logging.warning(f'Fim das páginas ou bloqueio na página {i}.')
                        with open(f"erro_pag_{i}.html", "w", encoding='utf-8') as f:
                            f.write(self.driver.page_source)
                        break

                    #now extracts each information of a single product and persists in a dictionary
                    for item in properties:
                        square_meters, status, price, address, rooms, furnished, link = 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A'
                        #getting all data about the property
                        try: 
                            original_price = item.find('span', class_='listing-search-item__price-main')
                            false_price = original_price.get_text(strip=True) if original_price else 'N/A'
                            price = float(false_price.replace('€', '').replace(',', '').replace('pcm', '').replace('.', ''))
                        except AttributeError:
                            price = 'N/A'
                            
                        try:
                            square_meters_element = item.find('li', class_='illustrated-features__item illustrated-features__item--surface-area')
                            square_meters_false = square_meters_element.get_text(strip=True) if square_meters_element else 'N/A'
                            square_meters = float(square_meters_false.replace('m²', ''))
                        except AttributeError:
                            square_meters = 'N/A'
                            
                        try:
        
                            #information about the property
                            status_element = item.find('span', class_='listing-label listing-label--featured')
                            address_element = item.find('div', class_='listing-search-item__sub-title')
                            link_element = item.find('a', class_='listing-search-item__link listing-search-item__link--title')
                            rooms_element = item.find('li', class_='illustrated-features__item illustrated-features__item--number-of-rooms')
                            furnished_element = item.find('li', class_='illustrated-features__item illustrated-features__item--interior')
                            
                            #cleaning data
                            address = address_element.get_text(strip=True) if address_element else 'N/A'
                            rooms = rooms_element.get_text(strip=True) if rooms_element else 'N/A'
                            status = status_element.get_text(strip=True) if status_element else 'disponible'
                            link = "https://www.pararius.com" + link_element['href'] if link_element else 'N/A'
                            furnished = furnished_element.get_text(strip=True) if furnished_element else 'N/A'
                            try:
                                price_per_square_meter = price // square_meters
                            except (TypeError, ValueError):
                                price_per_square_meter = "N/A"
                                

                            #saving in a dictionary
                            property = {
                                'address': address,
                                'rooms': rooms,
                                'status': status,
                                'price': price,
                                'link': link,
                                'square meters': square_meters,
                                'furnished status': furnished,
                                'price per square meter': price_per_square_meter,
                                'data of extraction': datetime.now().strftime("%d/%m/%Y %H:%M")
                            }

                            #add the property in a list
                            self.datas.append(property)
                   
                        except Exception as e: #error handling
                            logging.critical(f'detected error: {e}')

            except Exception as e:
                logging.error(f'detected error: {e}')
            finally:
                self.driver.quit()


    #persistence of data in google sheets, xlsx and csv
    def save_datas(self, name_file='scrap_properties.xlsx'):
        try:
            df = pd.DataFrame(self.datas)
            df.to_excel(name_file, index=False)
            df.to_csv('scrap_properties.csv', encoding='utf-8-sig', sep=';', index=False)
            google_datas = [list(item.values()) for item in self.datas]

            #error handling with limited rows
            size = 10
            total = len(google_datas)

            logging.info('starting upload for google sheets.')

            for i in range(0, total, size):
                batch = google_datas[i:i + size]
                planner.append_rows(batch)
                logging.info(f'lines {i} sent until {i + len(batch)}')
                sleep(2)
            
        except Exception as e:
            logging.critical(f'detected error in save datas: {e}')

#object
if __name__ == "__main__":
  scrap_properties = Scraper()
  #functions
  scrap_properties.take_datas()
  scrap_properties.save_datas()
