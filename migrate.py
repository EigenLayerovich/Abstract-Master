import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError

from db_api.database import db, Accounts, get_accounts
from data.config import logger


async def migrate():
    async with AsyncSession(db.engine) as session:

        # try:
        #     await session.execute(
        #         text("""
        #             ALTER TABLE accounts
        #             ADD COLUMN sahara_faucet DATETIME DEFAULT '1970-01-01 00:00:00';
        #         """)
        #     )
        # except OperationalError:
        #     pass

        try:
            await session.execute(
                text("""
                    ALTER TABLE accounts
                    ADD COLUMN abstract_twitter_connected BOOLEAN DEFAULT 0;
                """)
            )
        except OperationalError:
            pass

        try:
            await session.execute(
                text("""
                    ALTER TABLE accounts
                    ADD COLUMN bridge_complete BOOLEAN DEFAULT 0;
                """)
            )
        except OperationalError:
            pass

        try:
            await session.execute(
                text("""
                    ALTER TABLE accounts
                    ADD COLUMN abstract_discord_connected BOOLEAN DEFAULT 0;
                """)
            )
        except OperationalError:
            pass

        try:
            await session.execute(
                text("""
                    ALTER TABLE accounts
                    ADD COLUMN badge_twitter BOOLEAN DEFAULT 0;
                """)
            )
        except OperationalError:
            pass

        try:
            await session.execute(
                text("""
                    ALTER TABLE accounts
                    ADD COLUMN badge_discord BOOLEAN DEFAULT 0;
                """)
            )
        except OperationalError:
            pass

        try:
            await session.execute(
                text("""
                    ALTER TABLE accounts
                    ADD COLUMN badge_fund_your_account BOOLEAN DEFAULT 0;
                """)
            )
        except OperationalError:
            pass

        try:
            await session.execute(
                text("""
                    ALTER TABLE accounts
                    ADD COLUMN badge_the_trader BOOLEAN DEFAULT 0;
                """)
            )
        except OperationalError:
            pass

        try:
            await session.execute(
                text("""
                    ALTER TABLE accounts
                    ADD COLUMN abstract_pw_cookies TEXT DEFAULT '';
                """)
            )
        except OperationalError:
            pass

        try:
            await session.execute(
                text("""
                    ALTER TABLE accounts
                    ADD COLUMN abstract_pw_cookies_expired DATETIME DEFAULT '1970-01-01 00:00:00';
                """)
            )
        except OperationalError:
            pass

        try:
            await session.execute(
                text("""
                    ALTER TABLE accounts
                    ADD COLUMN abstract_pw_storage TEXT DEFAULT '';
                """)
            )
        except OperationalError:
            pass

        try:
            await session.execute(
                text("""
                    ALTER TABLE accounts
                    ADD COLUMN claimed_badges INTEGER DEFAULT 0;
                """)
            )
        except OperationalError:
            pass

        try:
            await session.execute(
                text("""
                    ALTER TABLE accounts
                    ADD COLUMN badges_parse_finished BOOLEAN DEFAULT 0;
                """)
            )
        except OperationalError:
            pass

        try:
            await session.execute(
                text("""
                    ALTER TABLE accounts
                    ADD COLUMN abstract_vote BOOLEAN DEFAULT 0;
                """)
            )
        except OperationalError:
            pass
        
        try:
            await session.execute(
                text("""
                    ALTER TABLE accounts
                    ADD COLUMN badge_app_voter BOOLEAN DEFAULT 0;
                """)
            )
        except OperationalError:
            pass

        try:
            await session.execute(
                text("""
                    ALTER TABLE accounts
                    ADD COLUMN abstract_swap DATETIME DEFAULT '1970-01-01 00:00:00';
                """)
            )
        except OperationalError:
            pass

        try:
            await session.execute(
                text("""
                    ALTER TABLE accounts
                    ADD COLUMN finished BOOLEAN DEFAULT 0;
                """)
            )
        except OperationalError:
            pass


        await session.commit()
        await session.close()

    logger.success('Migration completed.')
