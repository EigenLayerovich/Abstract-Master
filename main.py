import asyncio
import traceback
import random

from data.config import logger, tasks_lock, completed_tasks, remaining_tasks
from db_api.models import Accounts
from db_api.database import get_accounts
from settings.settings import SLEEP_BEETWEEN_ACTIONS, ACCOUNT_SHUFFLE
from tqdm import tqdm
from tasks.abstract import Abstract
from tasks.relay_bridge import RelayBridge


async def get_start(semaphore, quest: str):
    #try:

        accounts: list[Accounts] = await get_accounts(quest)

        # ДЛЯ ОПРЕДЛЕННОГО АККА
        # all_accounts: list[Accounts] = await get_accounts(quest)
        # accounts = []
        # for address in all_accounts:
        #     if address.evm_address == "":
        #         accounts.append(address)
        #         break
            
        if len(accounts) != 0:
            if ACCOUNT_SHUFFLE:
                random.shuffle(accounts)
            logger.info(f'Всего задач: {len(accounts)}')
            tasks = []
            if isinstance(quest, str):
                for account_data in accounts:
                    task = asyncio.create_task(start_limited_task(semaphore, accounts, account_data, quest=quest))
                    tasks.append(task)
            else:
                account_number = 1
                for account_data in accounts:
                    task = asyncio.create_task(start_limited_task(semaphore, accounts, account_data, quest=account_number))
                    tasks.append(task)
                    account_number += 1

            await asyncio.wait(tasks)
        else:
            msg = (f'Не удалось начать действие, причина: нет подходящих аккаунтов для выбранного действия.')
            logger.warning(msg)
    # except Exception as e:
    #     pass

async def start_limited_task(semaphore, accounts, account_data, quest):
    #try:
        async with semaphore:
            status = await start_task(account_data, quest)
            async with tasks_lock:
                completed_tasks[0] += 1
                remaining_tasks[0] = len(accounts) - completed_tasks[0]

            logger.warning(f'Всего задач: {len(accounts)}. Осталось задач: {remaining_tasks[0]}')

            if remaining_tasks[0] > 0 and status:
                # Генерация случайного времени ожидания
                sleep_time = random.randint(SLEEP_BEETWEEN_ACTIONS[0], SLEEP_BEETWEEN_ACTIONS[1])

                logger.info(f"Ожидание {sleep_time} между действиями...")
                
                await asyncio.sleep(sleep_time)

async def start_task(account_data, quest):

    if quest in {"🔹 Register Accounts"}:
        async with Abstract(data=account_data) as abstract:
            return await abstract.start_account_register()
    
    elif quest in {"🐦 Connect Twitter"}:
        async with Abstract(data=account_data) as abstract:
            return await abstract.start_connect_twitter()
        
    elif quest in {"👾 Connect Discord"}:
        async with Abstract(data=account_data) as abstract:
            return await abstract.start_connect_discord()
        
    elif quest in {"1) Relay"}:
        async with RelayBridge(data=account_data) as relay:
            return await relay.start_task()

    elif quest in {"Vote"}:
        async with Abstract(data=account_data) as abstract:
            return await abstract.start_vote()
        
    elif quest in {"Swap"}:
        async with Abstract(data=account_data) as abstract:
            return await abstract.start_swap()
        
    elif quest in {"Mix claim all eligible badges"}:
        async with Abstract(data=account_data) as abstract:
            return await abstract.start_mix_claim_eligible_badges()

    elif quest in {"Parse Badges Stats"}:
        async with Abstract(data=account_data) as abstract:
            return await abstract.start_parse_badges_stats()
        
    elif "Badge" in quest:
        badges_dict = {
            'Badge 1': {
                'id': 1,
                'name': "Connect Discord",
            },
            'Badge 2': {
                'id': 2,
                'name': "Connect Twitter / X", 
            },
            'Badge 3': {
                'id': 3,
                'name': "Fund Your Account",
            },
            'Badge 4': {
                'id': 4,
                'name': "App Voter"
            },
            'Badge 5': {
                'id': 5,
                'name': "The Trader"
            },
        }

        async with Abstract(data=account_data) as abstract:
            return await abstract.start_claim_badge(
                badge_id=badges_dict[quest]['id'],
                name=badges_dict[quest]['name'],
            )
    
