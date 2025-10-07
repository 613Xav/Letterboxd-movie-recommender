# scrape_letterboxd.py

import asyncio
import aiohttp
from aiohttp import ClientSession
from bs4 import BeautifulSoup
from selenium import webdriver
import time

# ─────── STEP 1: “Scrape all <film-slug> values from the user’s ‘Films’ page” ───────

def fetch_all_slugs(username: str, driver_path: str = None, headless: bool = True) -> list[str]:
    """
    Uses Selenium to open https://letterboxd.com/<username>/films/,
    waits briefly for React to populate the required clasess
    and then BeautifulSoup‐parses that HTML to extract every `data-film-slug`.
    Returns a list of slugs (e.g. ["sinners-2025", "mickey-17", …]).
    """
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless")
    # (You can replace with FirefoxOptions() + webdriver.Firefox() if you prefer.)
    driver = webdriver.Chrome(options=options, executable_path=driver_path) \
             if driver_path else webdriver.Chrome(options=options)
    driver.get(f"https://letterboxd.com/{username}/films/")
    
    # Wait a couple of seconds so React can inject the <ul>…<li> elements
    time.sleep(2)
    html = driver.page_source
    driver.quit()

    soup = BeautifulSoup(html, "lxml")
    # Note: the class here has to match exactly what Letterboxd uses:
    container_ul = soup.find(
        "ul",
        class_="poster-list -p70 -grid clear"
    )
    if not container_ul:
        raise RuntimeError("Could not find the <ul class='poster-list … film-list …'> in the HTML")
    
    slugs = []
    for li in container_ul.find_all("li", class_="poster-container"):
        # Each <li> has a <div … data-film-slug="…"> somewhere inside it
        div = li.find("div", class_="react-component poster film-poster linked-film-poster")
        if div and div.has_attr("data-film-slug"):
            slugs.append(div["data-film-slug"])
    return slugs


# ─────── STEP 2a: For each slug, fetch its main film page and parse out title/year/IMDb/TMDb ───────

async def fetch_film_page(slug: str, session: ClientSession) -> dict:
    """
    Fetches "https://letterboxd.com/film/{slug}/" and returns a dict:
      {
        "slug": slug,
        "title": …,
        "year": …,
        "imdb_id": …,   # e.g. "tt1234567" or "" if none
        "tmdb_id": …,   # e.g. "12345" or "" if none
      }
    """
    url = f"https://letterboxd.com/film/{slug}/"
    async with session.get(url) as resp:
        raw = await resp.text()
        soup = BeautifulSoup(raw, "lxml")

        result = {"slug": slug, "title": None, "year": None, "imdb_id": "", "tmdb_id": ""}
        # 1) The title + year live in <section id="featured-film-header">
        header_section = soup.find("section", {"id": "featured-film-header"})
        if header_section:
            h1 = header_section.find("h1")
            result["title"] = h1.get_text(strip=True) if h1 else None

            # Usually the year is inside <small class="number"><a>YYYY</a></small>
            try:
                year_tag = header_section.find("small", class_="number").find("a")
                result["year"] = int(year_tag.get_text(strip=True))
            except Exception:
                result["year"] = None

        # 2) The IMDb/TMDb external‐links (if present) have data-track-action="IMDb" or "TMDb"
        #    e.g. <a data-track-action="IMDb" href="https://www.imdb.com/title/…/">
        imdb_link_tag = soup.find("a", {"data-track-action": "IMDb"})
        if imdb_link_tag and imdb_link_tag.has_attr("href"):
            href = imdb_link_tag["href"]
            # IMDb URLs look like https://www.imdb.com/title/tt1234567/
            # so split out the “tt1234567” piece:
            try:
                result["imdb_id"] = href.split("/title/")[1].split("/")[0]
            except:
                result["imdb_id"] = ""

        tmdb_link_tag = soup.find("a", {"data-track-action": "TMDb"})
        if tmdb_link_tag and tmdb_link_tag.has_attr("href"):
            href = tmdb_link_tag["href"]
            # TMDb URLs look like https://www.themoviedb.org/movie/12345
            try:
                result["tmdb_id"] = href.split("/movie/")[1].split("/")[0]
            except:
                result["tmdb_id"] = ""

        return result


# ─────── STEP 2b: For each slug, fetch its poster via the AJAX endpoint ───────

async def fetch_poster_url(slug: str, session: ClientSession) -> str:
    """
    Fetches "https://letterboxd.com/ajax/poster/film/{slug}/hero/230x345/"
    and returns the raw poster‐image URL (no resizing query parameters).
    If it fails or there’s a fallback/“no‐poster”, returns "".
    """
    ajax_url = f"https://letterboxd.com/ajax/poster/film/{slug}/hero/230x345/"
    async with session.get(ajax_url) as resp:
        raw = await resp.text()
        soup = BeautifulSoup(raw, "lxml")

        try:
            img = soup.find("div", class_="film-poster").find("img")
            if not img or not img.has_attr("src"):
                return ""
            src = img["src"]
            # strip off any “?v=…” or other resize arguments:
            src = src.split("?")[0]
            # If it’s literally the default “empty”‐poster graphic, blank it out:
            if "empty-poster" in src:
                return ""
            return src
        except Exception:
            return ""


# ─────── STEP 3: Gather everything asynchronously ───────

async def gather_everything(slugs: list[str]) -> list[dict]:
    """
    Given a list of slugs, concurrently fetch (a) the film page and (b) the poster URL
    for each slug. Returns a list of combined dicts, e.g.:
      [
        {
          "slug": "sinners-2025",
          "title": "Sinners",
          "year": 2025,
          "imdb_id": "tt1234567",
          "tmdb_id": "54321",
          "poster_url": "https://a.ltrbxd.com/…/1116600-sinners-2025.jpg"
        },
        …
      ]
    """
    results: list[dict] = []

    # We’ll open ONE aiohttp.ClientSession for all requests
    async with aiohttp.ClientSession() as session:
        # 1) Fire off ALL film‐page fetches in parallel:
        film_page_tasks = [
            asyncio.create_task(fetch_film_page(slug, session))
            for slug in slugs
        ]
        # 2) Fire off ALL poster‐AJAX fetches in parallel:
        poster_tasks = [
            asyncio.create_task(fetch_poster_url(slug, session))
            for slug in slugs
        ]

        # Wait for all of them to finish:
        film_page_results = await asyncio.gather(*film_page_tasks)
        poster_results     = await asyncio.gather(*poster_tasks)

        # Now unify them one‐to‐one:
        for idx, slug in enumerate(slugs):
            film_info = film_page_results[idx]
            poster_url = poster_results[idx]
            film_info["poster_url"] = poster_url
            results.append(film_info)
            print(results)

    return results



# ─────── STEP 4: Put it all together in __main__ ───────

if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python scrape_letterboxd.py <letterboxd_username>")
        sys.exit(1)

    user = sys.argv[1]
    print(f"Fetching all film-slugs for {user}...")
    try:
        slugs = fetch_all_slugs(user)  
        print(f"  Found {len(slugs)} slugs.")
    except Exception as e:
        print("Error while scraping slugs:", e)
        sys.exit(1)

    # If you have 2000+ films, you might chunk this to avoid rate‐limiting:
    # e.g. chunk_size = 50, then do gather_everything on each chunk in a loop.
    # For simplicity, we'll just do them all at once here. 

    print("Now fetching film pages + poster URLs asynchronously…")
    movie_dicts = asyncio.run(gather_everything(slugs))

    # Dump to JSON on stdout (or write to a file)
    print(json.dumps(movie_dicts, indent=2))
    # Or: with open("my_films.json","w") as f: json.dump(movie_dicts, f, indent=2)

    print("Done.")










'''
# URL of the website
url = "https://quotes.toscrape.com/"

# Send GET request
response = requests.get(url)

# Check status
if response.status_code == 200:
    print("Success!")
else:
    print("Failed to fetch page.")

soup = BeautifulSoup(response.text, "lxml")  # or "html.parser"

# Find all quote containers
quotes = soup.find_all("div", class_="quote")

# Loop through each quote block
for quote in quotes:
    text = quote.find("span", class_="text").text
    author = quote.find("small", class_="author").text
    print(f"{text} — {author}")

'''






