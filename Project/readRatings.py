import asyncio
import aiohttp
import pprint
from aiohttp import ClientSession, TCPConnector
from bs4 import BeautifulSoup

def stars_to_score(star_str: str) -> int | None:
    """
    Convert a Letterboxd star string (e.g. "★★★½") into a 0–10 integer.
    """
    if not star_str:
        return None
    full = star_str.count("★")
    half = star_str.count("½")
    return full*2 + half

async def fetch_rating_info(
    username: str,
    max_pages: int = 50,
    concurrency: int = 20,
    timeout: float = 10.0
) -> list[dict]:
    """
    Scrape a user's Letterboxd film‑list pages via aiohttp.
    Returns a list of dicts with keys:
      slug, title, poster_url, rating, liked, display_name, year (None or int)
    """
    # Prepare a single session with connection pooling
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AsyncScraper/1.0)"
    }
    conn = TCPConnector(limit_per_host=concurrency)
    client_timeout = aiohttp.ClientTimeout(total=timeout)

    async with ClientSession(connector=conn, timeout=client_timeout, headers=headers) as session:
        all_films: list[dict] = []

        # 1) Fetch first page to get display name
        first_url = f"https://letterboxd.com/{username}/films/"
        async with session.get(first_url) as resp:
            text = await resp.text()
        root_soup = BeautifulSoup(text, "lxml")
        name_tag = root_soup.select_one("nav.profile-navigation h1.title-3")
        display_name = name_tag.get_text(strip=True) if name_tag else None
      

        # 2) Sequentially page through film‑list pages
        for page in range(1, max_pages + 1):
            url = f"https://letterboxd.com/{username}/films/by/date-earliest/page/{page}/"
            async with session.get(url) as resp:
                if resp.status != 200:
                    break
                status = resp.status    
                print(f"[DEBUG] GET {url} → {status}")
                page_html = await resp.text()

            if status != 200:
                print(f"[WARN] Non‑200 response on page {page}")


            soup = BeautifulSoup(page_html, "lxml")

            # find ul container
            ul = soup.find("ul", class_="grid -p70")
            if not ul:
                break

            items = ul.find_all("li", class_="griditem")
            #print(items)
            if not items:
                break

            #filling up film info
            for li in items:
                #print(li)

                # Get film info from the react component div (new structure)
                react_component = li.find("div", class_="react-component")
                if not react_component:
                    print("not info")
                    continue
                
                # Get slug from data-item-slug attribute (new structure)
                slug = react_component.get("data-item-slug")
                if not slug:
                    print("no slug found")
                    continue

                # Get title from data-item-name attribute (new structure)
                title = react_component.get("data-item-name")

                # rating 
                viewing_data = li.find("p", class_="poster-viewingdata")
                rating = None
                if viewing_data:
                    ratingLocation = viewing_data.find("span", class_="rating")
                    rating = stars_to_score(ratingLocation.get_text(strip=True)) if ratingLocation else None

                # liked? 
                liked = False
                if viewing_data:
                    liked_span = viewing_data.find("span", class_="like")
                    liked = bool(liked_span and "liked-micro" in liked_span.get("class", []))

                # poster URL
               # img = li.find("img")
               # poster_url = img["src"] if img and img.has_attr("src") else None

                all_films.append({
                    "slug":         slug,
                    "title":        title,
                    "poster_url":   None,
                    "display_name": display_name,
                    "rating":       rating,
                    "liked":        liked,
                    "year":         None,
                    "page":         page
                })
             
            """
        if fetch_years and all_films:
            # A) make a semaphore to limit concurrency
            year_sem = asyncio.Semaphore(concurrency)
            # B) helper to fetch & parse one film
            async def sem_fetch_year(film):
                async with year_sem:
                    detail_url = f"https://letterboxd.com/film/{film['slug']}/"
                    async with session.get(detail_url) as resp:
                        if resp.status == 200:
                            html = await resp.text()
                            film["year"] = parse_year_from_html(html)
                        else:
                            film["year"] = None


            # C) schedule one task per film
            tasks = [asyncio.create_task(sem_fetch_year(f)) for f in all_films]
        

            # D) wait for them all to finish
            await asyncio.gather(*tasks
            """

        return all_films
    
async def main():
    films = await fetch_rating_info(
        username= "613dbx"
    )
    pprint.pprint(films)
    
if __name__ == "__main__":
    asyncio.run(main())