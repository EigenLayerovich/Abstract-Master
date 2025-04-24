from datetime import datetime, timezone, timedelta

from sqlalchemy.future import select

from db_api import sqlalchemy_
from db_api.models import Accounts, Base
from data.config import ACCOUNTS_DB
from typing import List, Optional


db = sqlalchemy_.DB(f'sqlite+aiosqlite:///{ACCOUNTS_DB}', pool_recycle=3600, connect_args={'check_same_thread': False})


async def get_account(evm_pk: str) -> Optional[Accounts]:
    return await db.one(Accounts, Accounts.evm_pk == evm_pk)

async def get_accounts(
        quest: str
) -> List[Accounts]:

    if quest in {"🔹 Register Accounts"}:
        query = select(Accounts).where(
            Accounts.abstract_register == False,
            Accounts.finished != True
        )

    elif quest in {"🐦 Connect Twitter"}:
        query = select(Accounts).where(
            Accounts.abstract_twitter_connected == False,
            Accounts.twitter_token != '',
            Accounts.abstract_register == True,
            Accounts.finished != True
        )

    elif quest in {"👾 Connect Discord"}:
        query = select(Accounts).where(
            Accounts.abstract_discord_connected == False,
            Accounts.discord_token != '',
            Accounts.abstract_register == True,
            Accounts.finished != True
        )

    elif quest in {"1) Relay"}:
        query = select(Accounts).where(
            Accounts.bridge_complete == False,
            Accounts.abstract_register == True,
            Accounts.finished != True
        )

    # badges
    elif quest in {"Badge 1"}:
        query = select(Accounts).where(
            Accounts.badge_discord == False,
            Accounts.abstract_register == True,
            Accounts.finished != True
        )    

    elif quest in {"Badge 2"}:
        query = select(Accounts).where(
            Accounts.badge_twitter == False,
            Accounts.abstract_register == True,
            Accounts.finished != True
        )

    elif quest in {"Badge 3"}:
        query = select(Accounts).where(
            Accounts.badge_fund_your_account == False,
            Accounts.abstract_register == True,
            Accounts.finished != True
        )    

    elif quest in {"Badge 4"}:
        query = select(Accounts).where(
            Accounts.badge_app_voter == False,
            Accounts.abstract_register == True,
            Accounts.finished != True
        )    

    elif quest in {"Badge 5"}:
        query = select(Accounts).where(
            Accounts.badge_the_trader == False,
            Accounts.abstract_register == True,
            Accounts.finished != True
        )

    elif quest in {"Parse Badges Stats"}:
        query = select(Accounts).where(
            Accounts.badges_parse_finished == False,
            Accounts.abstract_register == True,
            Accounts.finished != True
        )

    elif quest in {"Vote"}:
        query = select(Accounts).where(
            Accounts.abstract_vote == False,
            Accounts.abstract_register == True,
            Accounts.finished != True
        )

    elif quest in {"Swap"}:

        now = datetime.now(timezone.utc)
        utc_now = now.replace(tzinfo=None)
        
        query = select(Accounts).where(
            Accounts.abstract_swap <= utc_now,
            Accounts.abstract_register == True,
            Accounts.finished != True
        )

    else:
        query = select(Accounts)   
    return await db.all(query)

async def initialize_db():
    await db.create_tables(Base)
