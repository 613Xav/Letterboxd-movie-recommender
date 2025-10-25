# ingest_ratings.py
import asyncio
import sys
from readRatings import fetch_rating_info
import database
import psycopg2
from psycopg2 import DatabaseError


async def insert_ratings(username: str):
    #Scrapes all movie of a user and the ratings
    films = await fetch_rating_info(username)

    # Prepare rows
    rating_rows = []
    movies_row = []
    for f in films:
        slug    = f["slug"]
        rating = float(f["rating"]) if f.get("rating") else None
        liked  = bool(f["liked"])
        if rating is not None:
            rating_rows.append((username, rating, liked, slug))
            movies_row.append((slug,))

    #preparing insertions for user pool table
    lastRating = films[-1]
    display_name = lastRating["display_name"]
    last_page = lastRating["page"]


    # Insert ratings into `ratings` table
    try:
        database.insert_ratings(rating_rows)
    except DatabaseError as e:
        print(f"[DB ERROR] Failed to insert ratings for {username!r}: {e}")
    else:
        print(f"Inserted/updated {len(rating_rows)} ratings for {username!r}")

    # Upsert into `user_pool` table
    last = films[-1]
    display_name = last["display_name"]
    last_page    = last["page"]

    try:
        database.upsert_user_pool(username, display_name, last_page)
    except DatabaseError as e:
        print(f"[DB ERROR] Failed to upsert user_pool for {username!r}: {e}")
    else:
        print(f"Upserted user_pool for {username!r}: page={last_page}, name={display_name!r}") 

    #prefill movies table
    try:
        database.prefill_movies(movies_row)
    except DatabaseError as e:
        print(f"[DB ERROR] Failed to insert movies in movie table: {e}")
    else:
        print(f"{len(movies_row)} movies inserted in movies table")



async def main(username: str):
   await insert_ratings(username)



if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_ratings.py <letterboxd_username>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))