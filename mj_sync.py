import os.path
import time

import argparse
import requests # request img from web
import shutil

from urllib.parse import urlparse
from pathlib import Path

from io import BytesIO

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
MJ_SC_TOP = MIDJOURNEY_SHOWCASE + "top/"
MJ_SC_RECENT = MIDJOURNEY_SHOWCASE + "recent/"
USER_AGENT = 'Mozilla/5.0 (Linux; Android 5.1.1; Nexus 5 Build/LMY48B; wv) AppleWebKit/537.36 (KHTML, like Gecko)  Version/4.0 Chrome/43.0.2357.65 Mobile Safari/537.36'
DATA_DIR = "data/"
QUERY_END = "/grid_0.png"
DEFAULT_PATH = "/home/pi/Pictures/Midjourney"

IMAGE_DB_BASE_OPT1 = "mj-gallery.com"
IMAGE_DB_BASE_OPT2 = "cdn.midjourney.com"

MJ_ICON_URL = "https://avatars.githubusercontent.com/u/61396273"
MJ_ICON_NAME = "mj.png"

TINT_COLOR = (0, 0, 0)  # Black
TRANSPARENCY = .25  # Degree of transparency, 0-100%
OPACITY = int(255 * TRANSPARENCY)

QR_CODE_SIZE = 200

# fetch MJ icon
MJ_ICON_IMAGE = None
try:
    r = requests.get(MJ_ICON_URL)
    MJ_ICON_IMAGE = Image.open(BytesIO(r.content)).convert('RGBA')
    newsize = (int(QR_CODE_SIZE/5), int(QR_CODE_SIZE/5))
    MJ_ICON_IMAGE = MJ_ICON_IMAGE.resize(newsize, Image.ANTIALIAS)
    draw = ImageDraw.Draw(MJ_ICON_IMAGE, "RGBA")
    draw.rectangle(((0, 0), (MJ_ICON_IMAGE.size[0], MJ_ICON_IMAGE.size[1])), outline=(255, 255, 255, 0), width=2)
    #MJ_ICON_IMAGE.show()
except Exception as e:
    print("Could not obtain MJ icon")
    del MJ_ICON_IMAGE


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


def fit_text(img, text, color, font, url, show_prompt):
    width = img.size[0] - 2
    draw = ImageDraw.Draw(img, "RGBA")
    pieces = list(break_fix(text, width, font, draw))
    draw_rec(img, draw, len(pieces), url, show_prompt)
    if show_prompt == 0:
        return
    height = sum(p[2] for p in pieces)
    if height > img.size[1]:
        raise ValueError("text doesn't fit")
    y = (img.size[1] - height)
    for t, w, h in pieces:
        x = (img.size[0] - w) // 2
        draw.text((x, y), t, font=font, fill=color)
        y += h


def draw_rec(img, draw, lines, url, show_prompt):
    width, height = img.size

    if show_prompt == 1:
        # transparent layer
        layer_height = lines*35
        #draw = ImageDraw.Draw(img, "RGBA")
        draw.rectangle(((0, height - layer_height), (width, height)), fill=(0, 0, 0, 127))
        draw.rectangle(((0, height - layer_height), (width, height)), outline=(255, 255, 255, 127), width=3)

    # qr code
    if url is not None:
        try:
            import qrcode
        except ImportError:
            print("qrcode lib not found")
            return

        # Creating an instance of qrcode
        qr = qrcode.QRCode(
            version=1,
            box_size=10,
            border=5)
        qr.add_data(url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color='white', back_color='transparent')
        newsize = (QR_CODE_SIZE, QR_CODE_SIZE)
        qr_img = qr_img.resize(newsize)
        qr_width, qr_height = qr_img.size
        if MJ_ICON_IMAGE is not None:
            # set size of QR code
            pos = ((qr_img.size[0] - MJ_ICON_IMAGE.size[0]) // 2,
                   (qr_img.size[1] - MJ_ICON_IMAGE.size[1]) // 2)
            qr_img.paste(MJ_ICON_IMAGE, pos)
        draw.rectangle(((width - qr_width, 0), (width, qr_height)), fill=(0, 0, 0, 127))
        draw.rectangle(((width - qr_width, 0), (width, qr_height)), outline=(255, 255, 255, 127), width=3)
        img.paste(qr_img, (width - qr_width, 0), qr_img.convert('RGBA'))


def edit_image(dest, prompt, url, args):
    img = Image.open(dest)
    # check aspect ratio here
    ar = img.size[0] / img.size[1]
    if args.orientation == "portrait_only":
        if ar > 1.0:
            print("Skipping " + dest + " due to aspect ratio missmatch")
            img.close()
            os.remove(dest)
            Path(dest).touch()
            return
    elif args.orientation == "landscape_only":
        if ar <= 1.0:
            print("Skipping " + dest + " due to aspect ratio missmatch")
            img.close()
            os.remove(dest)
            Path(dest).touch()
            return

    # text layer
    font = ImageFont.truetype("arial.ttf", 30)
    fit_text(img, prompt, (255, 255, 255), font, url if args.qr == 1 else None, args.show_prompts)

    # save and quit
    #img.show()
    img.save(dest + ".png")
    img.close()

    # remove tmp file
    os.remove(dest)


def download_elements(driver, gallery_dict, args):
    elements = driver.find_elements(By.TAG_NAME, 'img')
    WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, "img")))
    for child in elements:
        src_link = child.get_attribute("src")
        parsed_url = urlparse(src_link)
        if parsed_url.hostname == IMAGE_DB_BASE_OPT1:
            query_base = "https://" + IMAGE_DB_BASE_OPT1 + "/"
        elif parsed_url.hostname == IMAGE_DB_BASE_OPT2:
            query_base = "https://" + IMAGE_DB_BASE_OPT2 + "/"
        else:
            continue
        alt_txt = child.get_attribute("alt")
        #print(alt_txt)
        split_var = src_link.split("/")
        id = split_var[3]
        download_link = query_base + id + QUERY_END
        dest = os.path.join(args.path, id)

        # check if image is present in gallery
        if id in gallery_dict.keys():
            if args.sync == 0:
                continue
            if os.path.exists(dest) or os.path.exists(dest + ".png"):
                print("Image id " + id + " is already available in gallery")
                # set sync flag to True
                tmp_list = list(gallery_dict[id])
                tmp_list[0] = 1
                gallery_dict[id] = tuple(tmp_list)
                continue

        # download and bookmark image
        r = requests.get(download_link)
        with open(dest, 'wb') as outfile:
            outfile.write(r.content)
        print("Downloaded new file " + dest)
        # edit the image if needed
        edit_image(dest, alt_txt, download_link, args)
        # add new entry with sync flag enabled
        gallery_dict[id] = (1, dest)


def set_sync_flag(gallery_dict):
    for key in gallery_dict:
        tmp_list = list(gallery_dict[key])
        tmp_list[0] = 0
        gallery_dict[key] = tuple(tmp_list)


def evaluate_sync_flag(gallery_dict, old_dict_size):
    deletion_list = list()
    for key in gallery_dict:
        if gallery_dict[key][0] == 0:
            if os.path.exists(gallery_dict[key][1]):
                os.remove(gallery_dict[key][1])
            elif os.path.exists(gallery_dict[key][1] + ".png"):
                os.remove(gallery_dict[key][1] + ".png")
            deletion_list.append(key)
    # cleanup
    for idx in deletion_list:
        del gallery_dict[idx]

    print("Pre-fetch dict size: " + str(old_dict_size) + ", new dict size: " + str(len(gallery_dict)) + ", deleted entries: " + str(len(deletion_list)))


def scan_folder(path):
    gallery_dict = dict()
    import os
    for file in os.listdir(path):
        if file.endswith(".png"):
            split_list = file.split(".")
            id = split_list[0]
        else:
            id = file
        gallery_dict[id] = (1, os.path.join(path, id))
    return gallery_dict


def main():
    parser = argparse.ArgumentParser(description='MidJourney Sync Plugin')
    parser.add_argument('--path', type=str, default=DEFAULT_PATH, help="Path to your DynaFrame playlist folder")
    parser.add_argument('--seconds', type=int, default=3600, help="Seconds between MJ gallery syncs")
    parser.add_argument('--headless', type=int, default=1)
    parser.add_argument("--gallery", type=str, default="recent", help="-recent- to sync recently viewed MJ gallery, -top- to sync to sync hot list")
    parser.add_argument('--show_prompts', type=int, default=1, help="Enable to merge MJ text prompts into the image")
    parser.add_argument('--sync', type=int, default=1, help="Delete local images that are not available online if enabled, just add new images otherwise. User has to track memory usage.")
    parser.add_argument('--qr', type=int, default=0, help="Adds a QR code with the download link to the current image. Requires qrcode pip package installed")
    parser.add_argument("--orientation", type=str, default="portrait_only", help="Screen orientation to sort images by aspect ratio, -portrait_only- or -landscape_only- or -all-")
    args = parser.parse_args()

    # configure chrome, spoofing mobile device to get access to full resolution images
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

    # check if dir exists on startup

    if args.sync == 1:
        print("Sync flag enabled")
        if os.path.isdir(args.path):
            print("Removing existing MJ dir")
            shutil.rmtree(args.path)
        print("Creating new MJ dir")
        os.mkdir(args.path)
        # create bookkeeping dict
        # structure: id, (flag, path)
        gallery_dict = dict()
    else:
        print("Sync flag disabled, please keep track of your storage capacities")
        if os.path.isdir(args.path):
            gallery_dict = scan_folder(args.path)
        else:
            print("Creating new MJ dir")
            os.mkdir(args.path)
            # create bookkeeping dict
            # structure: id, (flag, path)
            gallery_dict = dict()

    target_url = MJ_SC_TOP if args.gallery == "top" else MIDJOURNEY_SHOWCASE

    while True:
        try:
            # Setting UserAgent as Chrome/83.0.4103.97
            #driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": 'Mozilla/5.0 (Linux; Android 5.1.1; Nexus 5 Build/LMY48B; wv) AppleWebKit/537.36 (KHTML, like Gecko)  Version/4.0 Chrome/43.0.2357.65 Mobile Safari/537.36'})
            # visit MJ url
            driver.get(target_url)

            # give driver time to reload the page
            time.sleep(10)

            if args.sync == 1:
                # reset sync flag of image gallery
                set_sync_flag(gallery_dict)
            old_dict_size = len(gallery_dict)

            # ugly: download first batch of images
            download_elements(driver, gallery_dict, args)

            # scroll shim
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            html = driver.find_element(By.TAG_NAME, 'html')
            html.send_keys(Keys.END)
            time.sleep(10)

            # ugly: download remaining images
            download_elements(driver, gallery_dict, args)

            if args.sync == 1:
                evaluate_sync_flag(gallery_dict, old_dict_size)

        except KeyboardInterrupt:
            print("Exiting via KB")
            driver.quit()
            return
        except Exception as e:
            print("Exception raised. No updates. Message: " + str(e))

        print("Finish synchronization round, next update in " + str(args.seconds) + " seconds")
        time.sleep(args.seconds)
    driver.quit()


if __name__ == '__main__':
    main()