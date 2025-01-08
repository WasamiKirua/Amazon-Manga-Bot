import mysql.connector
from mysql.connector import Error

from selenium import webdriver
#from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webdriver import BaseWebDriver, WebDriver
#from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from datetime import datetime
from dotenv import load_dotenv

import time
import socket
import requests
import re
import logging
import os

logger = logging.getLogger(__name__)  # the __name__ resolve to "uicheckapp.services"
load_dotenv()


def sleep(seconds):
    time.sleep(seconds)

def get_time():
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return current_time

def wait_for_db(host="mysql", port=3306, timeout=60):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=5):
                logger.info("******************")
                logger.info("Database is ready!")
                logger.info("******************")
                return True
        except (OSError, socket.error):
            logger.error("----")
            logger.error("Waiting for database connection...")
            logger.error("----")
            time.sleep(2)
    raise TimeoutError(f"Database not available after {timeout} seconds")

def create_connection(input_msg):
    clock = get_time()
    retries = 5
    while retries > 0:
        try:
            conn = mysql.connector.connect(
                host=os.getenv('MYSQL_HOST'),
                user=os.getenv('MYSQL_USER'),
                password=os.getenv('MYSQL_PASSWD'),
                database=os.getenv('DB')
            )
            if conn.is_connected():
                logger.info("****************************************************************")
                logger.info(f"{input_msg} successfully connected to MySQL database at {clock}")
                logger.info("****************************************************************")
                return conn
        except Error as e:
            logger.error("----")
            logger.error(f"{input_msg} failed to connect to DB. Retrying in 5 seconds... Error: {e}")
            logger.error("----")
            retries -= 1
            time.sleep(5)

    logger.error("----")
    logger.error(f"{input_msg} unabled to connect to MySQL after multiple attempts at {clock}")
    logger.error("----")
    return None

def close_connection(conn):
    if conn.is_connected():
        conn.close()

def create_tables():
    wait_for_db(host="mysql", port=3306)
    conn = create_connection(input_msg='Creation Table')
    cursor = conn.cursor()

    # SQL for creating the `manga` and `urls` tables
    create_manga_table = '''
        CREATE TABLE IF NOT EXISTS manga (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255),
            url TEXT,
            price DECIMAL(10, 2),
            availability VARCHAR(10),
            rating VARCHAR(10),
            trama TEXT,
            cover TEXT,
            cover_bin LONGBLOB
        );
    '''

    create_urls_table = '''
        CREATE TABLE IF NOT EXISTS urls (
            id INT AUTO_INCREMENT PRIMARY KEY,
            url TEXT
        );
    '''

    try:
        # Create both tables
        cursor.execute(create_manga_table)
        cursor.execute(create_urls_table)
        conn.commit()
        logger.info("****************************")
        logger.info("Tables created successfully!")
        logger.info("****************************")
    except Error as e:
        logger.error("----")
        logger.error(f"Error creating tables: {e}")
        logger.error("----")
    finally:
        close_connection(conn)

def add_url(url):
    try:
        conn = create_connection(input_msg='Add URL')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO urls (url) VALUES (%s)", (url,))
        conn.commit()
        logger.info("************************************")
        logger.info(f'Successfully added {url} to the DB!')
        logger.info("************************************")
    except Error as e:
        logger.error("----")
        logger.error(f"Error inserting Url: {e}")
        logger.error("----")
    finally:
        close_connection(conn)

def download_image(url):
    response = requests.get(url)
    if response.status_code == 200:
        logger.info("**************************************")
        logger.info(f"Image: {url} successfully downloaded!")
        logger.info("**************************************")
        return response.content  # Binary data of the image
    else:
        logger.error("----")
        logger.error(f"Failed to download image {url}. Status code: {response.status_code}")
        logger.error("----")

def url_scanner(driver: WebDriver):
    conn = create_connection(input_msg='URL Scanner')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, url FROM urls")
        urls = cursor.fetchall()
        if urls:
            for url_tuple in urls:
                url_id = url_tuple[0]
                url = url_tuple[1]

                driver.get(url)
                sleep(7)

                # Retrive Title
                v_n = driver.find_element(By.ID, 'productTitle')
                title = v_n.text

                # Retrive Availability
                try:
                    # Try to find the element with id 'outOfStock'
                    driver.find_element(By.ID, 'outOfStock')
                    # If found, set availability to 'No'
                    availability = 'No'
                except NoSuchElementException:
                    # If not found, the product is available
                    availability = 'Yes'

                # Retrive Price
                price = None
                try:
                    # Find the price element using JavaScript's querySelector
                    price_element = driver.execute_script(
                        'return document.querySelector(".a-section.a-spacing-none.aok-align-center.aok-relative span.aok-offscreen")'
                    )
                    # If not Null
                    if price_element:
                        # Get the text
                        price = driver.execute_script("return arguments[0].textContent", price_element)
                except NoSuchElementException:
                    # Catch exception if NoSuchElementException is raised
                    logger.error("----")
                    logger.error(f'Error retriving the Price for: {url} - {title}')
                    logger.error("----")

                # Ensure `price` has a default value if None
                if price is None:
                    price = ""  # Set price to an empty string if not found
                    availability = 'No'

                # Retrive Rating
                rating = None
                try:
                    rating = driver.find_element(By.ID, "acrPopover").text
                except NoSuchElementException:
                    rating = None
                    logger.error("----")
                    logger.error(f'Error retriving the Rating for: {url} - {title}')
                    logger.error("----")
                # Ensure `rating` has a default value if None
                if rating is None:
                    rating = ""  # Set price to an empty string if not found

                # Retrive Trama
                trama = None
                try:
                    book_description_div = driver.find_element(By.ID, "bookDescription_feature_div")
                    trama = book_description_div.find_element(By.TAG_NAME, "span").text
                except NoSuchElementException:
                    trama = None
                    logger.error("----")
                    logger.error(f'Error retriving the Trama for: {url} - {title}')
                    logger.error("----")
                

                # Retrive Cover
                cover_bin = None
                try:
                    image_element = driver.find_element(By.ID, 'landingImage')
                    image_url = image_element.get_attribute('src')
                    cover_bin = download_image(image_url) if image_url else None
                    # Download Cover
                    # cover_bin = download_image(image_url)
                except NoSuchElementException:
                    image_url = None
                    logger.error("----")
                    logger.error(f'Error retriving the Cover URL for: {url} - {title}')
                    logger.error("----")
        
                volume_json = {
                    "title": title,
                    "url": url,
                    "price": price,
                    "availability": availability,
                    "rating": rating,
                    "trama": trama,
                    "cover": image_url,
                    "cover_bin": cover_bin
                }

                # Clean price
                if price:
                    cleaned_price = re.sub(r'[^\d,]', '', price).replace(',', '.')
                    cleaned_price = float(cleaned_price) if cleaned_price else None
                else:
                    cleaned_price = 0.00

                if volume_json != None:
                    logger.info('*****************************************************************')
                    logger.info(f"JSON populated for URL {url} Manga's ID: {url_id}")
                    logger.info('*****************************************************************')

                # Insert into DB
                try:
                    # Prepare the SQL statement with placeholders
                    sql = '''
                    INSERT INTO manga (title, url, price, availability, rating, trama, cover, cover_bin)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    '''
                    # Execute the query with the values from volume_json as a tuple
                    # Prepare the values, replacing None with a suitable value (like `None` for SQL)
                    values = (
                        volume_json["title"],
                        volume_json["url"],
                        #cleaned_price,  # Clean whitespace from price
                        cleaned_price if cleaned_price else 0.00,
                        volume_json["availability"],
                        volume_json["rating"].replace(',', '.'),  # Replace comma with a dot for numeric format
                        volume_json["trama"],  # This can remain as None
                        volume_json["cover"],
                        volume_json["cover_bin"]
                    )
                    
                    if values != None:
                        logger.info('*****************************************************************')
                        logger.info(f"SQL Built for URL {url} Manga's ID: {url_id}")
                        logger.info('*****************************************************************')

                    # Execute Insert
                    try:
                        cursor.execute(sql, values)
                        conn.commit()
                        logger.info('*****************************************************************')
                        logger.info(f"Records added for Manga's ID:{url_id} to the DB")
                        logger.info('*****************************************************************')
                    except Error as e:
                        logger.error("----")
                        logger.error(f"Error: {e}")
                        logger.error("----")

                except Error as e:
                    logger.error("----")
                    logger.error(f"Error: {e}")
                    logger.error("----")
                sleep(3)

                delete_stmt = 'DELETE FROM urls WHERE id = %s'
                try:
                    cursor.execute(delete_stmt, (url_id,))
                    logger.info("*********************************************")
                    logger.info(f'Url: {url} with ID: {url_id} deleted from DB')
                    logger.info("*********************************************")
                    conn.commit()
                except Error as e:
                    logger.error("----")
                    logger.error(f'Error: {e}')
                    logger.error("----")

            logger.info('*******************')
            logger.info("All URLs processed.")
            logger.info('*******************')
        else:
            logger.info('***************')
            logger.info("No URLs found !")
            logger.info('***************')
    except Error as e:
        logger.error("----")
        logger.error(f"Error: {e}")
        logger.error("----")
    finally:
        close_connection(conn)

def send_to_telegram(message):
    logger.info("****************************")
    logger.info("Telegram Message")
    logger.info("****************************")
    apiToken = os.getenv('TELE_BOT_TOKEN')
    chatID = os.getenv('TELE_CHAT_ID')
    apiURL = f'https://api.telegram.org/bot{apiToken}/sendMessage'

    try:
        response = requests.post(apiURL, json={'chat_id': chatID, 'text': message})
        print(response.text)
    except Exception as e:
        print(e)
        logger.info("****************************")
        logger.info(f"Message not sent! {e}")
        logger.info("****************************")

def availability_scan(driver: WebDriver):
    conn = create_connection(input_msg='Availability Check')
    cursor = conn.cursor()
    query = 'SELECT * FROM manga'

    try:
        cursor.execute(query)
        manga_list = cursor.fetchall()
        if manga_list:
            for manga in manga_list:
                manga_id = manga[0]
                manga_url = manga[2]
                title = manga[1]
                cover = manga[7]
                availability_now = manga[4]

                logger.info("************************")
                logger.info(f"Processing: {manga_id} ")
                logger.info("************************")

                # Retrive URL
                driver.get(manga_url)
                sleep(7)

                if availability_now == 'No':
                    price = None
                    try:
                        # Find the price element using JavaScript's querySelector
                        price_element = driver.execute_script(
                            'return document.querySelector(".a-section.a-spacing-none.aok-align-center.aok-relative span.aok-offscreen")'
                        )
                        # If not Null
                        if price_element:
                            # Get the text
                            price = driver.execute_script("return arguments[0].textContent", price_element)
                    except NoSuchElementException:
                        # Catch exception if NoSuchElementException is raised
                        logger.info("*******************************************")
                        logger.info(f'Error retriving the Price for: {manga_url}')
                        logger.info("*******************************************")
                    # Ensure `price` has a default value if None
                    if price is None:
                        price = ""  # Set price to an empty string if not found
                    
                    if price:
                        cleaned_price = re.sub(r'[^\d,]', '', price).replace(',', '.')
                        cleaned_price = float(cleaned_price) if cleaned_price else None
                        logger.info("***************************************")
                        logger.info(f"Item ID: {manga_id} is back to stock !")
                        logger.info("***************************************")
                        availability = 'Yes'
                        ##TODO: Add logic to send Telegram message
                        tg_message_to_send = (
                            "Hei this Manga is back to stock!\n\n"
                            f"{manga_url}\n\n"
                            f"Title: {title}\n\n"
                            f"🔺Price: {price}€\n"
                            f"{cover}"
                        )

                        send_to_telegram(tg_message_to_send)

                        # Update the cover_bin, price and availability column
                        try:
                            update_query = "UPDATE manga SET price = %s, availability = %s WHERE id = %s"
                            # Execute Query
                            cursor.execute(update_query, (cleaned_price, availability, manga_id))
                            logger.info("**************************************************************************")
                            logger.info(f"ID: {manga_id} Updated! Price: {cleaned_price}, Available: {availability}")
                            logger.info("**************************************************************************")
                            # Commit to DB
                            conn.commit()
                        except Error as e:
                            logger.error("----")
                            logger.error(f"Error: {e}")
                            logger.error("----")
                        sleep(5)
                    else:
                        cleaned_price = 0.00
                        logger.info("**************************")
                        logger.info("Item Still unavailable ...")
                        logger.info(f"Price: {cleaned_price}")
                        logger.info("**************************")
                else:
                    logger.info("***********************************************")
                    logger.info(f"Manga ID: {manga_id} Is Available ... Skipping")
                    logger.info("***********************************************")
    except Error as e:
        logger.error("----")
        logger.error(f"Error: {e}")
        logger.error("----")
    finally:
        close_connection(conn)

def scan_url_call():
    logger.info("*******************")
    logger.info("URL Scanner Started")
    logger.info("*******************")
    yourScrapedDataUrls = None
    ff_options = webdriver.FirefoxOptions()
    ff_options.add_argument('--no-sandbox')
    ff_options.add_argument("headless")
    ff_options.add_argument('--disable-dev-shm-usage')

    try:
        # DONT CHANGE THIS LINE
        driver_urls = webdriver.Remote("http://selenium:4444/wd/hub", options=ff_options)
        yourScrapedDataUrls = url_scanner(driver_urls)
    except Exception as e:
        logger.error("----")
        logger.error(e)
        logger.error("----")
    finally:
        driver_urls.quit()
    return yourScrapedDataUrls

def availability_call():
    logger.info("****************************")
    logger.info("Availability Scanner Started")
    logger.info("****************************")
    yourScrapedDataUrls = None
    ff_options = webdriver.FirefoxOptions()
    ff_options.add_argument('--no-sandbox')
    ff_options.add_argument("headless")
    ff_options.add_argument('--disable-dev-shm-usage')

    try:
        # DONT CHANGE THIS LINE
        driver_availability = webdriver.Remote("http://selenium:4444/wd/hub", options=ff_options)
        yourScrapedDataUrls = availability_scan(driver_availability)
    except Exception as e:
        logger.error("----")
        logger.error(e)
        logger.error("----")
    finally:
        driver_availability.quit()
    return yourScrapedDataUrls