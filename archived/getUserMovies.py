import asyncio
import aiohttp
import pprint 
from aiohttp import ClientSession
from bs4 import BeautifulSoup
from selenium import webdriver


def parse_year_from_html(html: str) -> str | None:
    """
    Parse the release year from a movie detail page HTML.
    """
    soup = BeautifulSoup(html, "lxml")
    span = soup.find("span", class_="releasedate")
    if span:
        a = span.find("a")
        if a and a.text:
            return a.text.strip()
    return None

async def fetch_year(session: ClientSession, slug: str) -> str | None:
    """
    Fetch the movie detail page for a given slug and extract the release year.
    """
    url = f"https://letterboxd.com/film/{slug}/"
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                html = await resp.text()
                return parse_year_from_html(html)
    except Exception:
        return None
    return None

def stars_to_score(star_str: str) -> int | None:
    """
    Convert a Letterboxd star string (e.g. "★★★★", "★★★½", "") 
    into an integer 0–10 score, or None if no rating.
    """
    if not star_str:
        return None

    full = star_str.count("★")
    half = star_str.count("½")
    # Cap in case something odd slipped through
    full = min(full, 5)
    half = min(half, 1)

    return full * 2 + half

async def fetch_rating_info(
    username: str,
    max_pages: int = 50,
    driver_path: str = None,
    headless: bool = True,
    fetch_years: bool = False
) -> list[dict]:
    """
    Async version of fetch_movie_info.  All blocking Selenium calls
    are run in a thread-pool so as not to block asyncio's event loop.

    If fetch_years is True, the function will visit each movie's slug URL
    to retrieve and fill in the 'year' field.
    """
    loop = asyncio.get_running_loop()

    # set up Chrome *in a thread*
    def _make_driver():
        opts = webdriver.ChromeOptions()
       #if headless:
           # opts.add_argument("--headless")
        opts.add_argument("--no-proxy-server")
        opts.add_argument("--proxy-bypass-list=*")
                          
        if driver_path:
            return webdriver.Chrome(options=opts, executable_path=driver_path)
        else:
            return webdriver.Chrome(options=opts)

    driver = await loop.run_in_executor(None, _make_driver)
    all_films: list[dict] = []

    #get the user display name. will be added to every dict for quicker operations as it can be retrieved from the initial soup 

    try: 
        url = f"https://letterboxd.com/{username}/films/"

        await loop.run_in_executor(None, driver.get,url)
        await asyncio.sleep(1.5)
        html = await loop.run_in_executor(None, lambda: driver.page_source)
        soup = BeautifulSoup(html, "lxml")

        displayNameLocation = soup.find("nav", class_ = "profile-navigation").find("h1", class_ ="title-3")
        displayName = displayNameLocation.get_text(strip=True) if displayNameLocation else None

    except Exception as e:
        # handle/log the error, then skip to the next page
        print(f"failed display name retrieval for {username} exception:{e}")

    

    try:
        for page in range(1, max_pages + 1):
            url = f"https://letterboxd.com/{username}/films/by/date-earliest/page/{page}/"

            # navigate → in thread
            await loop.run_in_executor(None, driver.get, url)
            # give React time to render
            await asyncio.sleep(1.5)

            # grab HTML
            html = await loop.run_in_executor(None, lambda: driver.page_source)
            soup = BeautifulSoup(html, "lxml")

            ul = soup.find("ul", class_="poster-list -p70 -grid clear")
            if not ul:
                break

            items = ul.find_all("li", class_="poster-container")
            if not items:
                break

            for li in items:
                print(li)
                filmInfo = li.find(
                    "div",
                    class_="react-component poster film-poster linked-film-poster"
                )
                ratingLocation = li.find("span", class_="rating")
                rating = ratingLocation.get_text(strip=True) if ratingLocation else None
                rating = stars_to_score(rating)


                likedTag = li.find(
                    "span", class_="like liked-micro has-icon icon-liked icon-16"
                )
                liked = bool(likedTag)

                posterLocation = li.find("img", class_ = "image")
                posterURL  = posterLocation.get("src")


                if not filmInfo:
                    continue

                all_films.append({
                    "slug":       filmInfo.get("data-film-slug"),
                    "title":      filmInfo.get("data-film-name"),
                    "year":       None,
                    "poster_url": posterURL,
                    "rating":     rating,
                    "liked":      liked,
                    "display_name": displayName if displayName else None
                })
    finally:
        # quit driver
        await loop.run_in_executor(None, driver.quit)

    # Optionally fetch years for each slug
    if fetch_years and all_films:
        semaphore = asyncio.Semaphore(25)
        async with aiohttp.ClientSession() as session:
            async def sem_fetch(film):
                async with semaphore:
                    film["year"] = await fetch_year(session, film["slug"])
            await asyncio.gather(*(sem_fetch(f) for f in all_films))

    return all_films



async def main():
    films = await fetch_rating_info("613dbx", headless=False)
    pprint.pprint(films[:5])
    print("…", len(films) - 5, "more")
    #pprint(films)

if __name__ == "__main__":
    asyncio.run(main())
