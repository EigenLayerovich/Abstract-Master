import os
import ast

from dotenv import load_dotenv
from data.config import logger
from distutils.util import strtobool

load_dotenv()

try:
    # КОЛ-ВО ПОПЫТОК
    NUMBER_OF_ATTEMPTS: int = int(os.getenv('NUMBER_OF_ATTEMPTS'))

    # Одновременное кол-во асинхронных задач
    ASYNC_TASK_IN_SAME_TIME: int = int(os.getenv('ASYNC_TASK_IN_SAME_TIME'))
    
    USE_PRIVATE_KEYS_ENCRYPTION: bool = bool(strtobool(os.getenv('USE_PRIVATE_KEYS_ENCRYPTION')))

    # ADD_TWITTER
    ADD_TWITTER: bool = bool(strtobool(os.getenv('ADD_TWITTER')))
    ADD_DISCORD: bool = bool(strtobool(os.getenv('ADD_DISCORD')))

    # ключи от сервисов капчи
    SERVICE_TO_USE: str = str(os.getenv('SERVICE_TO_USE'))
    HCAPTCHA_SERVICE_TO_USE: str = str(os.getenv('HCAPTCHA_SERVICE_TO_USE'))
    API_KEY_CAPMONSTER: str = str(os.getenv('API_KEY_CAPMONSTER'))
    API_KEY_CAPSOLVER: str = str(os.getenv('API_KEY_CAPSOLVER'))
    API_KEY_24_CAPTCHA: str = str(os.getenv('API_KEY_24_CAPTCHA'))
    API_KEY_BESTCAPTCHA: str = str(os.getenv('API_KEY_BESTCAPTCHA'))

    # SLEEP BEETWEEN ACTION
    SLEEP_FROM: int = int(os.getenv('SLEEP_FROM'))
    SLEEP_TO: int = int(os.getenv('SLEEP_TO'))
    SLEEP_BEETWEEN_ACTIONS: list = [SLEEP_FROM, SLEEP_TO]

    ACCOUNT_SHUFFLE: bool = bool(strtobool(os.getenv('ACCOUNT_SHUFFLE')))

    PERCENT_NATIVE_TO_TX = os.getenv('PERCENT_NATIVE_TO_TX')
    if PERCENT_NATIVE_TO_TX:
        PERCENT_NATIVE_TO_TX = ast.literal_eval(PERCENT_NATIVE_TO_TX) 
    MIN_BALANCE = float(os.getenv('MIN_BALANCE'))

    # RELAY BRIDGE
    RELAY_BRIDGE_NETWORK_APPLY = {
        "Arbitrum": bool(strtobool(os.getenv('RELAY_BRIDGE_ARBITRUM'))),
        "Optimism": bool(strtobool(os.getenv('RELAY_BRIDGE_OPTIMISM'))),
        "Base":  bool(strtobool(os.getenv('RELAY_BRIDGE_BASE'))),
        "Ethereum":  bool(strtobool(os.getenv('RELAY_BRIDGE_ETHEREUM'))),
    }
    AMOUNT_TO_BRIDGE = os.getenv('AMOUNT_TO_BRIDGE')
    if AMOUNT_TO_BRIDGE:
        AMOUNT_TO_BRIDGE = ast.literal_eval(AMOUNT_TO_BRIDGE) 

    DEPOSIT_ALL_BALANCE = bool(strtobool(os.getenv('DEPOSIT_ALL_BALANCE')))

    MIN_AMOUNT_IN_NETWORK = os.getenv('MIN_AMOUNT_IN_NETWORK')
    if MIN_AMOUNT_IN_NETWORK:
        MIN_AMOUNT_IN_NETWORK = ast.literal_eval(MIN_AMOUNT_IN_NETWORK)

    MIN_AMOUNT_TO_BRIDGE: float = float(os.getenv('MIN_AMOUNT_TO_BRIDGE'))

    MAX_RELAY_SLIPPAGE: int = int(float(os.getenv('MAX_RELAY_SLIPPAGE')) * 100)

    
    # SWAP SETTINGS

    NEXT_SWAP_AFTER_DAYS = os.getenv('NEXT_SWAP_AFTER_DAYS')
    if MIN_AMOUNT_IN_NETWORK:
        NEXT_SWAP_AFTER_DAYS = ast.literal_eval(NEXT_SWAP_AFTER_DAYS)
    
    ABS_SWAP_SLIPPAGE: float =  int(float(os.getenv('ABS_SWAP_SLIPPAGE')) * 100)

    ETH_SWAP_TO = os.getenv('ETH_SWAP_TO')
    if ETH_SWAP_TO:
        ETH_SWAP_TO = ast.literal_eval(ETH_SWAP_TO)

    NATIVE_ETH_TO_SWAP = os.getenv('NATIVE_ETH_TO_SWAP')
    if NATIVE_ETH_TO_SWAP:
        NATIVE_ETH_TO_SWAP = ast.literal_eval(NATIVE_ETH_TO_SWAP)

    USE_STATIC_AMOUNT = bool(strtobool(os.getenv('USE_STATIC_AMOUNT')))
    
    MIN_TOKEN_SWAP_USD_VALUE: float =  float(os.getenv('MIN_TOKEN_SWAP_USD_VALUE'))

    SWAP_ONLY_TOKEN_TO_ETH = bool(strtobool(os.getenv('SWAP_ONLY_TOKEN_TO_ETH')))

except TypeError:
    logger.warning('Вы не создали .env и не добавили туда настройки')