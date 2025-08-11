# db.py
import os
from contextlib import contextmanager
from psycopg2 import pool, OperationalError
from psycopg2.extras import execute_values

DB_HOST     = os.getenv("PGHOST", "localhost")
DB_PORT     = os.getenv("PGPORT", "5432")
DB_NAME     = os.getenv("PGDATABASE", "recc-db")
DB_USER     = os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("PGPASSWORD", "admin")


# Initialize a connection pool
try:
    _pool = pool.SimpleConnectionPool(
        minconn=1,
        maxconn=5,
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
except OperationalError as e:
    raise RuntimeError(f"Could not initialize Postgres pool: {e}")

@contextmanager
def get_conn():
    """
    Context manager that yields a pooled psycopg2 connection.
    """
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)

def insert_ratings(ratings):
    sql = """
        INSERT INTO ratings (user_id, rating, liked, movie_id)
        VALUES %s
        ON CONFLICT DO NOTHING
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, ratings)
        conn.commit()
    
    

def insert_movies(films):
    """
    Bulk-insert a list of (movie_id, title, poster_link, release_year, rating_amount) tuples.
    On conflict, increment the existing rating_amount by the incoming rating_amount.
    """
    sql = """
      INSERT INTO movies 
        (movie_id, title, poster_link, release_year, rating_amount)
      VALUES %s
      ON CONFLICT (movie_id) DO UPDATE
        SET rating_amount = movies.rating_amount + EXCLUDED.rating_amount,
            title         = COALESCE(EXCLUDED.title, movies.title),
            poster_link   = COALESCE(EXCLUDED.poster_link, movies.poster_link),
            release_year  = COALESCE(EXCLUDED.release_year, movies.release_year)
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, films)
        conn.commit()

def prefill_movies(movies):
    """
    prefill movies that will later be scraped to fill up information 

    """

    sql = """ INSERT INTO MOVIES (movie_id) 
              VALUES %s
              ON CONFLICT (movie_id) DO NOTHING 
            """
    with get_conn() as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, movies)
        conn.commit()

def upsert_user_pool(user_id: str, display_name: str, last_page: int = 0):
    sql = """
      INSERT INTO user_pool (user_id, username, last_page_scraped)
      VALUES (%s, %s, %s)
      ON CONFLICT (user_id) DO UPDATE
        SET username          = EXCLUDED.username,
            last_page_scraped = EXCLUDED.last_page_scraped;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (user_id, display_name, last_page))
        conn.commit()

    


if __name__ == "__main__":
    try:
        # Use the context manager to borrow (and automatically return) a conn
        with get_conn() as conn:
            params = conn.get_dsn_parameters()
            print("Connected to database:", params["dbname"])
            print("Search path:", params["options"])
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                print("🗄️  PostgreSQL version:", version)
    except Exception as e:
        print("Connection failed:", e)
    else:
        print("Connection successful!")