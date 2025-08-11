import database
import pandas as pd
from ingestRatings import main as ingest_main 
import asyncio


# Read just the “UserIDs” column from the first sheet:
def get_user_list() -> list:
    userIds = pd.read_excel(
        "C:/Users/Praxede/Downloads/uni/LetterboxdProject/data/UsersToScrape.xlsx",        # path to your Excel file
        sheet_name="Feuil1",        # or the sheet name as a string
        usecols=["UserIDs"], # only load that one column
        dtype={"UserIDs": str},  # ensure they’re read as strings
        skiprows=0,
        nrows = 32
    )
    return userIds



async def build_database(userList):
    for userId in userList.UserIDs:
        await ingest_main(userId)

async def main():

    userList = get_user_list()
    await build_database(userList)
            






if __name__ == "__main__" :
    asyncio.run(main())




