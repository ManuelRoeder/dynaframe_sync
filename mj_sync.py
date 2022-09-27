import os.path
import time

import argparse
import requests # request img from web
import shutil

from urllib.parse import urlparse
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait

# Importing the PIL library
from PIL import Image
from PIL import ImageDraw, ImageFont

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

MIDJOURNEY_SHOWCASE = "https://www.midjourney.com/showcase/"
USER_AGENT = 'Mozilla/5.0 (Linux; Android 5.1.1; Nexus 5 Build/LMY48B; wv) AppleWebKit/537.36 (KHTML, like Gecko)  Version/4.0 Chrome/43.0.2357.65 Mobile Safari/537.36'
DATA_DIR = "data/"
QUERY_BASE = "https://mj-gallery.com/"
QUERY_END = "/grid_0.png"
DEFAULT_PATH = "/home/pi/Pictures/Midjourney"

TINT_COLOR = (0, 0, 0)  # Black
TRANSPARENCY = .25  # Degree of transparency, 0-100%
OPACITY = int(255 * TRANSPARENCY)


def break_fix(text, width, font, draw):
    if not text:
        return
    lo = 0
    hi = len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        t = text[:mid]
        w, h = draw.textsize(t, font=font)
        if w <= width:
            lo = mid
        else:
            hi = mid - 1
    t = text[:lo]
    w, h = draw.textsize(t, font=font)
    yield t, w, h
    yield from break_fix(text[lo:], width, font, draw)


def fit_text(img, text, color, font):
    width = img.size[0] - 2
    draw = ImageDraw.Draw(img, "RGBA")
    pieces = list(break_fix(text, width, font, draw))
    draw_rec(img,draw,len(pieces))
    height = sum(p[2] for p in pieces)
    if height > img.size[1]:
        raise ValueError("text doesn't fit")
    y = (img.size[1] - height)
    for t, w, h in pieces:
        x = (img.size[0] - w) // 2
        draw.text((x, y), t, font=font, fill=color)
        y += h


def draw_rec(img, draw, lines):
    width, height = img.size
    # transparent layer
    layer_height = lines*35
    #draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle(((0, height - layer_height), (width, height)), fill=(0, 0, 0, 127))
    draw.rectangle(((0, height - layer_height ), (width, height)), outline=(255, 255, 255, 127), width=3)


def edit_image(dest, prompt):
    img = Image.open(dest)
    # text layer
    font = ImageFont.truetype("arial.ttf", 30)
    fit_text(img,prompt,(255,255,255),font)

    # save and quit
    #img.show()
    img.save(dest)


def download_elements(driver, args):
    elements = driver.find_elements(By.TAG_NAME, 'img')
    WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, "img")))
    for child in elements:
        src_link = child.get_attribute("src")
        parsed_url = urlparse(src_link)
        if not parsed_url.hostname == "mj-gallery.com":
            continue
        alt_txt = child.get_attribute("alt")
        print(alt_txt)
        split_var = src_link.split("/")
        id = split_var[3]
        download_link = QUERY_BASE + id + QUERY_END
        dest = os.path.join(args.path, id + ".png")
        if not os.path.exists(dest):
            r = requests.get(download_link)
            with open(dest, 'wb') as outfile:
                outfile.write(r.content)
            print("Downloaded file " + dest)
            if args.show_prompts == 1:
                edit_image(dest, alt_txt)


def main():
    parser = argparse.ArgumentParser(description='Midjourney Sync')
    parser.add_argument('--path', type=str, default=DEFAULT_PATH, help="Path to your DynaFrame sync folder")
    parser.add_argument('--seconds', type=int, default=3600, help="Seconds between MJ gallery syncs")
    parser.add_argument('--headless', type=int, default=1)
    parser.add_argument("--gallery", type=str, default="recent", help="-recent- to sync recently viewed MJ gallery, -top- to sync to sync hot list")
    parser.add_argument('--show_prompts', type=int, default=1, help="Enable to merge MJ text prompts into the image")
    args = parser.parse_args()

    # configure chrome
    mobile_emulation = {"deviceName": "Pixel 2"}
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_experimental_option("mobileEmulation", mobile_emulation)
    chrome_options.add_experimental_option('w3c', True)
    if args.headless == 1:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(5)

    # check if dir exists
    if os.path.isdir(args.path):
        print("Removing existing MJ dir")
        shutil.rmtree(args.path)
    print("Creating new MJ dir")
    os.mkdir(args.path)

    while True:
        try:
            # Setting UserAgent as Chrome/83.0.4103.97
            #driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": 'Mozilla/5.0 (Linux; Android 5.1.1; Nexus 5 Build/LMY48B; wv) AppleWebKit/537.36 (KHTML, like Gecko)  Version/4.0 Chrome/43.0.2357.65 Mobile Safari/537.36'})
            # visit team url
            driver.get(MIDJOURNEY_SHOWCASE)

            if args.gallery == "top":
                # find and press recent button
                driver.find_element("xpath", "/html/body/div[1]/div[1]/div[2]/div/div[2]/div/div/div/button[2]").click()

            #print(driver.execute_script("return navigator.userAgent;"))

            download_elements(driver, args)

            print("Scroll shim")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            html = driver.find_element(By.TAG_NAME, 'html')
            html.send_keys(Keys.END)
            time.sleep(10)

            download_elements(driver, args)

        except KeyboardInterrupt:
            print("Exiting via KB")
            driver.quit()
            return
        except Exception as e:
            print("Exception raised. No updates. Message: " + str(e))

        print("Finish dl round")
        time.sleep(args.seconds)
    driver.quit()


if __name__ == '__main__':
    main()