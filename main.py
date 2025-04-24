import sys
import itertools

import asyncio

from data.config import logger
from utils.create_files import create_files
from db_api.database import initialize_db
from utils.adjust_policy import set_windows_event_loop_policy
from data.config import EVM_PKS, PROXIES, EMAIL_DATA, TWITTER_TOKENS, DISCORD_TOKENS, logger
from utils.import_info import get_info
from utils.user_menu import get_action, abstract_menu, bridge_menu, badges_menu, onchain_menu
from db_api.start_import import ImportToDB
from settings.settings import ASYNC_TASK_IN_SAME_TIME
from tasks.main import get_start
from migrate import migrate
from utils.reset_count_progress import set_progress_to_zero
from utils.encrypt_params import check_encrypt_param


def main():
    global remaining_tasks

    while True:
        set_progress_to_zero()

        user_choice = get_action()

        semaphore = asyncio.Semaphore(ASYNC_TASK_IN_SAME_TIME)

        match user_choice:

            case "Import data to db":

                evm_pks = get_info(EVM_PKS)
                proxies = get_info(PROXIES)
                emails = get_info(EMAIL_DATA)
                twitter_tokens = get_info(TWITTER_TOKENS)
                discord_tokens = get_info(DISCORD_TOKENS)

                logger.info(f'\n\n\n'
                            f'Загружено в evm_pks.txt {len(evm_pks)} аккаунтов EVM \n'
                            f'Загружено в proxies.txt {len(proxies)} прокси \n'
                            f'Загружено в emails.txt {len(emails)} прокси \n'
                            f'Загружено в twitter_tokens.txt {len(twitter_tokens)} прокси \n'
                            f'Загружено в discord_tokens.txt {len(discord_tokens)} прокси \n'
                )

                cycled_proxies_list = itertools.cycle(proxies) if proxies else None

                formatted_data: list = [{
                        'evm_pk': evm_pk,
                        'proxy': next(cycled_proxies_list) if cycled_proxies_list else None,
                        'email': emails.pop(0) if emails else None,
                        'twitter_token': twitter_tokens.pop(0) if twitter_tokens else None,
                        'discord_token': discord_tokens.pop(0) if discord_tokens else None,
                    } for evm_pk in evm_pks
                ]

                asyncio.run(ImportToDB.add_info_to_db(accounts_data=formatted_data))

            case "Abstract":
                abstract_choice = abstract_menu()
                match abstract_choice:
                    case "🏆 Badges":
                        badges_choice = badges_menu()
                        match badges_choice:
                            case "Mix claim all eligible badges":
                                asyncio.run(get_start(semaphore, "Mix claim all eligible badges"))

                            case "Connect Discord":
                                asyncio.run(get_start(semaphore, "Badge 1"))

                            case "Connect Twitter / X":
                                asyncio.run(get_start(semaphore, "Badge 2"))
                                
                            case "Fund Your Account":
                                asyncio.run(get_start(semaphore, "Badge 3"))

                            case "App Voter":
                                asyncio.run(get_start(semaphore, "Badge 4"))
                            
                            case "The Trader":
                                asyncio.run(get_start(semaphore, "Badge 5"))

                            case "Parse Badges Stats":
                                asyncio.run(get_start(semaphore, "Parse Badges Stats"))

                    case "🔗 Onchain":
                        onchain_choice = onchain_menu()
                        match onchain_choice:
                            case "Vote":
                                asyncio.run(get_start(semaphore, "Vote"))

                            case "Swap":
                                asyncio.run(get_start(semaphore, "Swap"))


                    case "🔹 Register Accounts":
                        asyncio.run(get_start(semaphore, "🔹 Register Accounts"))

                    case "🐦 Connect Twitter":
                        asyncio.run(get_start(semaphore, "🐦 Connect Twitter"))

                    case "👾 Connect Discord":
                        asyncio.run(get_start(semaphore, "👾 Connect Discord"))

                    case "🌉 Bridge":
                        bridge_choice = bridge_menu()
                        match bridge_choice:
                            case "1) Relay":
                                asyncio.run(get_start(semaphore, "1) Relay"))


            case "Exit":
                sys.exit(1)


if __name__ == "__main__":
    #try:
        check_encrypt_param()
        asyncio.run(initialize_db())
        create_files()
        asyncio.run(migrate())
        set_windows_event_loop_policy()
        main()
    # except (SystemExit, KeyboardInterrupt):
    #     logger.info("Program closed")