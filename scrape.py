import os
import re
import html
from typing import Dict, List
import pandas as pd
import threading
from tqdm import tqdm
import requests
from lxml import html as htmll

BASE_URL = "https://receptite.com/%D0%BA%D0%B0%D1%82%D0%B0%D0%BB%D0%BE%D0%B7%D0%B8-%D1%81-%D1%80%D0%B5%D1%86%D0%B5%D0%BF%D1%82%D0%B8"
OUT_FILENAME = "bg-recipes.tsv"

def main():
    scraped_data = {
        "title": [],
        "rating": [],
        "complexity": [],
        "products": [],
        "description": [],
        "image": [],
        "times_cooked": [],
        "fav": [],
        "category": [],
    }
    response = requests.get(BASE_URL).text

    # Get HTML with all recipe categories.
    base_html = re.findall(
        r"shapka_head.+?search_konteineri\"([^~]+)dude2_head", response
    )[0]
    categories_urls = re.findall(r"(https:\/\/receptite\.com\/.+?)\"", base_html)

    progressbar = tqdm(categories_urls)

    # Scrape each category in `BASE_URL`.
    for cat_url in progressbar:
        cat_html = requests.get(cat_url).text
        try:
            n_pages = get_n_pages(cat_html)
        # When the category has only a single page of recipes.
        except Exception:
            n_pages = 1

        progressbar.set_description(f"Num. pages: {n_pages}")

        threads = []
        # Iterate through each page in the category.
        for page in range(n_pages):
            page_url = f"{cat_url}/{page + 1}"
            page_html = requests.get(page_url).text

            recipes_urls = re.findall(
                r"class=\"zagS\".*?><a[^>]+href=\"([^\"]+)\"", page_html
            )

            t = threading.Thread(target=scrape_url, args=(recipes_urls, scraped_data))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

    df = pd.DataFrame.from_dict(data=scraped_data)
    print("Dataframe:\n", df.head())

    df.to_csv(OUT_FILENAME, sep="\t")
    print(f"Output file created at {OUT_FILENAME}")

 # Scrape each recipe in `cat_url`.
def scrape_url(recipes_urls, scraped_data):
    for recipe_url in recipes_urls:
        try:
            recipe_data = scrape_recipe(recipe_url)
            scraped_data = append_scraped_data(scraped_data, recipe_data)
        except Exception as e:
            print(f"Error occurred: {e}")

def get_n_pages(category_html):
    pages_block = re.findall(r"class=\"pages_bar\"[^>]+>(.+?)<\/div", category_html)[0]
    last_page_num = re.findall(
        r"<a\s+href=\"[^\"]+\/(\d+)\"\s*>\s*\d+\s*<", pages_block
    )[-1]

    return int(last_page_num)


def scrape_recipe(recipe_url: str):
    src = requests.get(recipe_url)
    tree = htmll.fromstring(src.content)

    title = get_title(tree)
    rating = get_rating(tree)
    complexity = get_complexity(tree)
    products = get_products(tree)

    image = get_image(tree)
    times_cooked = get_times_cooked(tree)
    fav = get_fav(tree)
    description = get_description(tree)
    category = get_category(html.unescape(src.text))

    recipeObject =  {
        "title": title,
        "rating": rating,
        "complexity": complexity,
        "products": products,
        "description": description,
        "image": image,
        "times_cooked": times_cooked,
        "fav": fav,
        "category": category
    }
    
    return recipeObject


def get_title(src) -> str:
    title = src.xpath(f'//div[contains(@class, "title_rec_big")]')[0].text_content().strip()
    return title


def get_rating(src) -> int:
    rating = src.xpath(f'(//i[text()="Рейтинг:"]//following-sibling::img)[1]')
    return int(rating[0].attrib['title'])


def get_complexity(src) -> int:
    complexity = src.xpath(f'(//i[text()="Сложност:"]//following-sibling::img)[1]')[0].get('src')
    return int(re.findall(r"(\d+)", complexity)[0])


def get_products(src) -> []:
    ingredients =  src.xpath(f'//li[@itemprop="ingredients"]')
    ingredients_list = [ ingr.text_content() for ingr in ingredients ]

    return ingredients_list


def get_description(src) -> str:
    recipe = src.xpath(f'//div[@class="recepta_prigotviane"]')[0].text_content().strip()
    return recipe


def get_image(src: str) -> str:
    image = ''
    try:
        image = src.xpath(f'//img[@alt="виж снимката"]')[0].get('src')
    except:
        image = "https://receptite.com/graphs/nophoto.png"

    return image

def get_times_cooked(src) -> int:
    tries = 0
    try:
        tries = int(src.xpath(f'(//i[text()="Изпробвана:"]//following-sibling::b)[1]')[0].text_content())
    except Exception as e:
        print(e)
    
    return tries


def get_fav(src) -> int:
    fav = 0
    try:
        fav = int(src.xpath(f'//i[text()="Любима на"]//following-sibling::b')[0].text_content())
    except Exception as e:
        print(e)
    
    return fav


def get_category(src) -> str:
    category = re.findall(r'itemprop="recipeCategory"\s+content="([^"]*?)"\s*([^>]+)', src)[0]
    category = ' '.join([str(elem) for elem in category]).replace('/', '')
    return category


def append_scraped_data(
    scraped_data: Dict[str, List[str]], recipe_data: Dict[str, str]
):
    for dtype in scraped_data:
        scraped_data[dtype].append(recipe_data[dtype])

    return scraped_data


if __name__ == "__main__":
    main()
