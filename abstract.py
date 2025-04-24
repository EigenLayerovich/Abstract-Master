import os
import json
import uuid
import random
import aiofiles
import asyncio
import secrets
from datetime import datetime, timezone, timedelta
from eth_account.messages import encode_defunct
from functools import wraps
from urllib.parse import urlparse, parse_qs

from clients.eth.eth_client import EthClient
from tasks.base import Base
from db_api.database import Accounts
from utils.encrypt_params import get_private_key
from data.config import logger, tasks_lock, BADGE_STATUS, BADGE_ABI, VOTE_ABI
from tasks.abstract_pw import PlaywrightCompleter
from utils.encrypt_params import get_encrypted_pk
from clients.twitter.twitter_client import TwitterClient
from clients.discord.discord_client import DiscordClient
from data.models import Networks, TokenAmount, BADGE_CONTRACT, VOTE_CONTRACT, Token, SWAP_TOKENS, DefaultABIs
from settings.settings import (
    MIN_BALANCE, 
    ETH_SWAP_TO, 
    USE_STATIC_AMOUNT, 
    NATIVE_ETH_TO_SWAP, 
    PERCENT_NATIVE_TO_TX, 
    MIN_TOKEN_SWAP_USD_VALUE, 
    ABS_SWAP_SLIPPAGE,
    NEXT_SWAP_AFTER_DAYS,
    SWAP_ONLY_TOKEN_TO_ETH
)
from utils.get_amount import get_amount


class Abstract(Base):

    def __init__(self, data: Accounts):
        super().__init__(data)

        self.eth_client = EthClient(
            private_key=get_private_key(data), proxy=self.data.proxy, user_agent=self.data.user_agent, network=Networks.Abstract
        )

        # authenticate_request
        self.token = ''
        self.refresh_token = ''
        self.user_id = ''
    
        # session_request
        self.identity_token = ''

        # wallet verif
        self.privy_address = ''
        self.smart_wallet_address = ''

    @staticmethod
    def get_uuid():
        return str(uuid.uuid4())
    
    @staticmethod
    def get_current_utc_timestamp():
        return datetime.now(timezone.utc).replace(microsecond=963000).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    def get_privi_io_base_headers(self):
        return {
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://www.abs.xyz',
            'priority': 'u=1, i',
            'privy-app-id': 'cm04asygd041fmry9zmcyn5o5',
            'privy-ca-id': self.get_uuid(),
            'privy-client': 'react-auth:2.0.10-beta-20250127063316',
            'privy-client-id': 'client-WY5amHUxxFHMHHMmPJvBQgGPJQ1WuMFjP57qUmHcbu4g2',
            'referer': 'https://www.abs.xyz/',
            'sec-ch-ua': f'"Not_A Brand";v="8", "Chromium";v="{self.version}", "Google Chrome";v="{self.version}"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': f'"{self.platform}"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'user-agent': self.data.user_agent,
        }
    
    async def init_request(self):

        json_data = {
            'address': self.data.evm_address,
        }

        response = await self.async_session.post(
            'https://auth.privy.io/api/v1/siwe/init', 
            headers=self.get_privi_io_base_headers(), 
            json=json_data
        )

        if response.status_code == 200:
            return True, response.json()
        logger.error(f'[{self.data.id}] | {self.data.evm_address} | не смог создать init запрос на подключение к abstract.xyz. Status code: {response.status_code} | Ответ сервера: {response.text}')
        return False, ''

    async def authenticate_request(self, answer):

        message = (
            'www.abs.xyz wants you to sign in with your Ethereum account:\n'
            f'{self.data.evm_address}\n\n'
            'By signing, you are proving you own this wallet and logging in. This does not initiate a transaction or cost any fees.\n\n'
            'URI: https://www.abs.xyz\n'
            'Version: 1\n'
            'Chain ID: 1\n'
            f'Nonce: {answer['nonce']}\n'
            f'Issued At: {self.get_current_utc_timestamp()}\n'
            'Resources:\n- https://privy.io'
        )

        message_encoded = encode_defunct(text=message)
        signed_message = self.eth_client.account.sign_message(message_encoded)


        json_data = {
            'message': message,
            'signature': signed_message.signature.hex(),
            'chainId': 'eip155:1',
            'walletClientType': 'metamask',
            'connectorType': 'injected',
            'mode': 'login-or-sign-up',
        }

        response = await self.async_session.post(
            'https://auth.privy.io/api/v1/siwe/authenticate', 
            headers=self.get_privi_io_base_headers(), 
            json=json_data
        )

        if response.status_code == 200:
            self.token = response.json().get('token', '')
            self.refresh_token = response.json().get('refresh_token', '')
            self.user_id = response.json().get('user', {}).get('id', '')
            wallets = response.json().get("user", {}).get("linked_accounts", [])
            self.privy_address = wallets[1].get("address") if len(wallets) > 1 else None

            if all([self.token, self.refresh_token, self.user_id]):
                return True
        logger.error(f'[{self.data.id}] | {self.data.evm_address} | не смог создать authenticate запрос на подключение к abstract.xyz. Status code: {response.status_code} | Ответ сервера: {response.text}')
        return False

    async def session_request(self):

        headers = self.get_privi_io_base_headers()
        headers['authorization'] = f'Bearer {self.token}'


        json_data = {
            'refresh_token': self.refresh_token,
        }

        response = await self.async_session.post(
            'https://auth.privy.io/api/v1/sessions', 
            headers=headers, 
            json=json_data
        )

        if response.status_code == 200:
            self.identity_token = response.json().get('identity_token', '')
            self.smart_wallet_address = response.json().get('user', {}).get('custom_metadata', {}).get('walletAddress', '')
            if self.identity_token and self.smart_wallet_address:
                return True
        logger.error(f'[{self.data.id}] | {self.data.evm_address} | не смог создать session запрос на подключение к abstract.xyz. Status code: {response.status_code} | Ответ сервера: {response.text}')
        return False

    async def login(self):
        status, answer = await self.init_request()
        if status:
            status = await self.authenticate_request(answer)
            if status:
                return await self.session_request()
        return False

    @staticmethod
    def open_session(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
                status = await self.login()
                if status:
                    return await func(self, *args, **kwargs)
        return wrapper
    
    def get_abs_portal_base_headers(self):
        return {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9',
            'authorization': f'Bearer {self.token}',
            'cache-control': 'no-cache',
            'origin': 'https://www.abs.xyz',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://www.abs.xyz/',
            'sec-ch-ua': f'"Google Chrome";v="{self.version}", "Chromium";v="{self.version}", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': f'"{self.platform}"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': self.data.user_agent,
            'x-privy-token': self.identity_token,
        }

    async def get_user_info(self):

        response = await self.async_session.post('https://backend.portal.abs.xyz/api/user', headers=self.get_abs_portal_base_headers(), json={})
        if response.status_code == 200:
            return True, response.json()
        
        logger.error(f'[{self.data.id}] | {self.data.evm_address} | не смог получить user info. Status code: {response.status_code} | Ответ сервера: {response.text}')
        return False, False

    async def check_pw_cookies(self, playwright):
        now = datetime.now(timezone.utc)
        utc_now = now.replace(tzinfo=None)

        if not self.data.abstract_pw_cookies or not self.data.abstract_pw_storage or self.data.abstract_pw_cookies_expired < utc_now:
            status, cookies, storage = await playwright.update_cookies()
            if not status:
                logger.error(f'[{self.data.id}] | {self.data.evm_address} | не смог создать или обновить куки для работы с PW')
                return False
            
            self.data.abstract_pw_cookies = cookies
            self.data.abstract_pw_storage = storage
            self.data.abstract_pw_cookies_expired = datetime.now(timezone.utc) + timedelta(days=365)
            async with tasks_lock:
                await self.write_to_db()

        return True


    @Base.retry
    async def start_account_register(self):
        
        playwright = PlaywrightCompleter(self.data)

        status = await self.check_pw_cookies(playwright)

        if status:

            status, smart_wallet, privy_pk = await playwright.start_register()

            if status:

                await self.login()

                privy_client = EthClient(
                    private_key=privy_pk, proxy=self.data.proxy, user_agent=self.data.user_agent
                )

                if self.smart_wallet_address == smart_wallet and self.privy_address == privy_client.account.address:
                    self.data.privy_pk = get_encrypted_pk(privy_pk)
                    self.data.privy_address = privy_client.account.address
                    self.data.abstract_smartwallet = smart_wallet
                    self.data.abstract_register = True
                    async with tasks_lock:
                        await self.write_to_db()

                    logger.success(f'[{self.data.id}] | {self.data.evm_address} | аккаунт успешно прошел регистрацию и подтянул privy_address, privy_pk, smart_wallet_address в бд')
                    return True

            return False
    
    async def get_connect_twitter_url(self):
        json_data = {
            'isInitialFlow': False,
        }

        response = await self.async_session.post('https://backend.portal.abs.xyz/api/social/twitter', headers=self.get_abs_portal_base_headers(), json=json_data)
        if response.status_code == 200:
            url = response.json().get('authUrl', '')
            if url:
                return True, url
            
        logger.error(f'[{self.data.id}] | {self.data.evm_address} | не смог создать запрос на получение twitter url. Status code: {response.status_code} | Ответ сервера: {response.text}')
        return False, ''

    async def get_twitter_client(self):
        self.twitter_client = TwitterClient(
            data=self.data, 
            session=self.async_session,
            version=self.version,
            platform=self.platform
        )
        status, msg = await self.twitter_client.login()
        if not status and msg != 'OK':
            logger.error(f'[{self.data.id}] | {self.data.evm_address} | {msg}')
            self.data.twitter_account_status = self.twitter_client.account_status
            async with tasks_lock:
                await self.write_to_db()
            return False
        return True
    
    async def confirm_redirect_uri(self, redirect_uri, base='https://twitter.com/'):
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'no-cache',
            'priority': 'u=0, i',
            'referer': base,
            'sec-ch-ua': f'"Not A(Brand";v="8", "Chromium";v="{self.version}", "Google Chrome";v="{self.version}"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': f'"{self.platform}"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'cross-site',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': self.data.user_agent,
        }

        response = await self.async_session.get(redirect_uri, headers=headers)
        if response.status_code == 200:
            return True
        return False

    @Base.retry
    @open_session
    async def start_connect_twitter(self):
        
        status, user_info = await self.get_user_info()
        twitter = user_info.get('user', {}).get('socials', {}).get('twitter', '')
        if not twitter:
            status, url = await self.get_connect_twitter_url()
            if status:
                status = await self.get_twitter_client()
                if status:
            
                    parsed_url = urlparse(url)
                    params = parse_qs(parsed_url.query)

                    params = {k: v[0] if len(v) == 1 else v for k, v in params.items()}
                    status, auth_code = await self.twitter_client.start_oauth2(url, params)
                    if status:
                        status, redirect_uri = await self.twitter_client.confirm_oauth2(url, auth_code)
                        if status: 
                            await self.confirm_redirect_uri(redirect_uri)
                            await asyncio.sleep(10)
                            status, user_info = await self.get_user_info()
                            twitter = user_info.get('user', {}).get('socials', {}).get('twitter', '')
                        else:
                            logger.error(f'[{self.data.id}] | {self.data.evm_address} | {redirect_uri}')
                            return False
                    else:
                        logger.error(f'[{self.data.id}] | {self.data.evm_address} | {auth_code}')
                        return False

                else:
                    return True
                
        if twitter:
            self.data.abstract_twitter_connected = True
            async with tasks_lock:
                await self.write_to_db()
            logger.success(f'[{self.data.id}] | {self.data.evm_address} | успешно привязал твиттер к abstract')
            return True
        else:
            logger.error(f'[{self.data.id}] | {self.data.evm_address} | не смог привязать твиттер к abstract')

        return False
    
    async def get_connect_discord_url(self):
        json_data = {
            'isInitialFlow': False,
        }
  
        response = await self.async_session.post('https://backend.portal.abs.xyz/api/social/discord', headers=self.get_abs_portal_base_headers(), json=json_data)

        if response.status_code == 200:
            url = response.json().get('authUrl', '')
            if url:
                return True, url
            
        logger.error(f'[{self.data.id}] | {self.data.evm_address} | не смог создать запрос на получение discord url. Status code: {response.status_code} | Ответ сервера: {response.text}')
        return False, ''
    
    @Base.retry
    @open_session
    async def start_connect_discord(self):
        
        status, user_info = await self.get_user_info()
        discord = user_info.get('user', {}).get('socials', {}).get('discord', '')
        if not discord:
            status, url = await self.get_connect_discord_url()
            if status:
                discord_client = DiscordClient(self.data, self.async_session, self.version, self.platform)
                parsed_url = urlparse(url)
                params = parse_qs(parsed_url.query)

                params = {k: v[0] if len(v) == 1 else v for k, v in params.items()}
                status, answer = await discord_client.start_oauth2(url, params)
                if status:
                    status, redirect_uri = await discord_client.confirm_oauth2(url, params)
                    if status: 
                        await self.confirm_redirect_uri(redirect_uri)
                        await asyncio.sleep(10)
                        status, user_info = await self.get_user_info()
                        discord = user_info.get('user', {}).get('socials', {}).get('discord', '')
                    else:
                        logger.error(f'[{self.data.id}] | {self.data.evm_address} | {redirect_uri}')
                        return False
                else:
                    logger.error(f'[{self.data.id}] | {self.data.evm_address} | {answer}')
                    return False
            else:
                return True
                
        if discord:
            self.data.abstract_discord_connected = True
            async with tasks_lock:
                await self.write_to_db()
            logger.success(f'[{self.data.id}] | {self.data.evm_address} | успешно привязал discord к abstract')
            return True
        else:
            logger.error(f'[{self.data.id}] | {self.data.evm_address} | не смог привязать discord к abstract')
    
        return False
    
    async def check_if_badge_is_claimed(self, badge_id):

        response = await self.async_session.post(
            f'https://backend.portal.abs.xyz/api/badge/{badge_id}/validate', 
            headers=self.get_abs_portal_base_headers(), 
            json={}
        )
        if response.status_code == 200:
            is_claimed = response.json().get('isClaimed', '')
            return True, is_claimed
        logger.error(f'[{self.data.id}] | {self.data.evm_address} | не смог проверить через validate был бейдж заклеймлен или нет...')
        return False, False

    async def check_smart_wallet_balance(self):
        abstact_client = EthClient(
            private_key=get_private_key(self.data),
            network=Networks.Abstract,
            user_agent=self.data.user_agent, 
            proxy=self.data.proxy
        )
        
        return TokenAmount(await abstact_client.w3.eth.get_balance(self.data.abstract_smartwallet), wei=True)
    
    # @Base.retry
    # @open_session
    # async def start_claim_badge(self, badge_id, name):

    #     need_write_to_db = False
    #     need_success_msg = False

    #     status, already_claimed = await self.check_if_badge_is_claimed(badge_id=badge_id)

    #     if not already_claimed:
    
    #         smart_wallet_balance = await self.check_smart_wallet_balance()
    #         if float(smart_wallet_balance.Ether) < MIN_BALANCE:
    #             logger.error(
    #                 f'[{self.data.id}] | {self.data.evm_address} | баланс smart wallet меньше MIN_BALANCE. '
    #                 f'Клейм не возможен. Smart wallet balance: {smart_wallet_balance.Ether} | MIN_BALANCE: {MIN_BALANCE}'
    #             )
    #             return True
            
    #         playwright = PlaywrightCompleter(self.data)
    #         status = await self.check_pw_cookies(playwright)
    #         if status:

    #             status = await playwright.claim_badge(name)
    #             if status:
    #                 status, already_claimed = await self.check_if_badge_is_claimed(badge_id=badge_id)
    #                 if status and already_claimed:
    #                     need_write_to_db = True
    #                     need_success_msg = True
    #                 else:
    #                     logger.error(f'[{self.data.id}] | {self.data.evm_address} | не смог заклеймить bage {name}')

    #     elif status and already_claimed:
    #         need_write_to_db = True
    #         logger.warning(f'[{self.data.id}] | {self.data.evm_address} | badge {name} уже был успешно склеймлен!')

    #     if need_write_to_db:
    #         badge_mapping = {
    #             1: "badge_discord",
    #             2: "badge_twitter",
    #             3: "badge_fund_your_account",
    #             5: "badge_the_trader",
    #         }

    #         if badge_id in badge_mapping:
    #             setattr(self.data, badge_mapping[badge_id], True)

    #         async with tasks_lock:
    #             await self.write_to_db()

    #         if need_success_msg:
    #             logger.success(f'[{self.data.id}] | {self.data.evm_address} | badge {name} успешно склеймлен!')
            
    #         return True
    #     return False
    

    async def _start_claim_badge(self, badge_id, name):
        need_write_to_db = False
        need_success_msg = False

        status, already_claimed = await self.check_if_badge_is_claimed(badge_id=badge_id)

        if not already_claimed:
            
            response = await self.async_session.post(
                f"https://backend.portal.abs.xyz/api/badge/{badge_id}/claim",
                headers=self.get_abs_portal_base_headers(),
                json={}
            )
            
            if response.status_code == 200:
                signature = response.json().get('signature', '')
                if not signature:
                    logger.error(f'[{self.data.id}] | {self.data.evm_address} | не смог получить signature для клейма badge')
                    return False
                
                logger.info(f'[{self.data.id}] | {self.data.evm_address} | пробую заклеймить badge {name}...')

                badge_contract = self.eth_client.w3.eth.contract(address=BADGE_CONTRACT, abi=json.load(open(BADGE_ABI)))
                encoded_data = badge_contract.encodeABI(
                    fn_name="mintBadge",
                    args=[self.smart_wallet_address, badge_id, signature]
                )

                transaction = {
                    "chain": Networks.Abstract.chain_id,
                    "from": self.data.abstract_smartwallet,
                    "to": BADGE_CONTRACT,
                    "data": encoded_data,
                    "value": 0
                }

                status, msg = await self.eth_client.send_abstract_tx(self.async_session, self.data, transaction)
                if not status:
                    logger.error(f'[{self.data.id}] | {self.data.evm_address} | {msg}')
                    return False
                
                logger.success(f"[{self.data.id}] | {self.data.evm_address} | Транзакция успешно выполнена! Хэш: {Networks.Abstract.explorer}{msg}")
                await asyncio.sleep(5)
                status, already_claimed = await self.check_if_badge_is_claimed(badge_id=badge_id)
                if status and already_claimed:
                    need_write_to_db = True
                    need_success_msg = True
                else:
                    logger.error(f'[{self.data.id}] | {self.data.evm_address} | не смог заклеймить bage {name}')
                    return False
                
            else:
                logger.error(f'[{self.data.id}] | {self.data.evm_address} | не смог получить signature. Status code: {response.status_code} | Ответ сервера: {response.text}')
                return False

        elif status and already_claimed:
            need_write_to_db = True
            logger.warning(f'[{self.data.id}] | {self.data.evm_address} | badge {name} уже был успешно склеймлен!')

        if need_write_to_db:
            badge_mapping = {
                1: "badge_discord",
                2: "badge_twitter",
                3: "badge_fund_your_account",
                4: "badge_app_voter",
                5: "badge_the_trader",
            }

            if badge_id in badge_mapping:
                setattr(self.data, badge_mapping[badge_id], True)
            else:
                logger.warning(f'[{self.data.id}] | {self.data.evm_address} | информация про badge не будет записана в бд...')
                return True

            async with tasks_lock:
                await self.write_to_db()

            if need_success_msg:
                logger.success(f'[{self.data.id}] | {self.data.evm_address} | badge {name} успешно склеймлен!')
            
            return True
        return False

    @Base.retry
    @open_session
    async def start_claim_badge(self, badge_id, name):
    
        smart_wallet_balance = await self.check_smart_wallet_balance()
        if float(smart_wallet_balance.Ether) < MIN_BALANCE:
            logger.error(
                f'[{self.data.id}] | {self.data.evm_address} | баланс smart wallet меньше MIN_BALANCE. '
                f'Клейм не возможен. Smart wallet balance: {smart_wallet_balance.Ether} | MIN_BALANCE: {MIN_BALANCE}'
            )
            return True

        await self.get_user_info()

        return await self._start_claim_badge(badge_id, name)

    @staticmethod
    def sort_badges_info(badges_list):
        available_to_claim = []
        for badge in badges_list:
            if badge['claimed'] == True:
                continue
            available_to_claim.append({
                'name': badge['badge']['name'],
                'id': badge['badge']['id']
            })

        return available_to_claim

    @Base.retry
    @open_session
    async def start_mix_claim_eligible_badges(self):
        status, info = await self.get_user_info()
        if not status:
            return False
        
        badges = info.get("user", {}).get("badges", [])
        if not badges:
            logger.warning(f'[{self.data.id}] | {self.data.evm_address} | нет доступных баджей для клейма...')
            return True

        available_to_claim = self.sort_badges_info(badges)
        if not available_to_claim:
            logger.warning(f'[{self.data.id}] | {self.data.evm_address} | нет доступных баджей для клейма...')
            return True
        
        smart_wallet_balance = await self.check_smart_wallet_balance()
        if float(smart_wallet_balance.Ether) < MIN_BALANCE:
            logger.error(
                f'[{self.data.id}] | {self.data.evm_address} | баланс smart wallet меньше MIN_BALANCE. '
                f'Клейм не возможен. Smart wallet balance: {smart_wallet_balance.Ether} | MIN_BALANCE: {MIN_BALANCE}'
            )
            return True
        
        logger.info(f'[{self.data.id}] | {self.data.evm_address} | доступно {len(available_to_claim)} баджей для клейма. Начинаю клейм...')
        while available_to_claim:
            badge = random.choice(available_to_claim) 
            available_to_claim.remove(badge) 

            status = await self._start_claim_badge(badge['id'], badge['name'])
            if not status:
                return False
            if len(available_to_claim) > 0:
                sleep_time = random.randint(30, 60)
                logger.info(f'[{self.data.id}] | {self.data.evm_address} | осталось {len(available_to_claim)} баджей для клейма | сон {sleep_time} после успешного действия...')
                await asyncio.sleep(sleep_time)

            status, info = await self.get_user_info()
            if not status:
                return False
            
            badges = info.get("user", {}).get("badges", [])
            if not badges:
                logger.warning(f'[{self.data.id}] | {self.data.evm_address} | нет доступных баджей для клейма...')
                return True

            available_to_claim = self.sort_badges_info(badges)
            if not available_to_claim:
                logger.warning(f'[{self.data.id}] | {self.data.evm_address} | нет доступных баджей для клейма...')
                return True
            
        return True

    @staticmethod
    async def load_badge_data():
        if os.path.exists(BADGE_STATUS):
            async with aiofiles.open(BADGE_STATUS, "r", encoding="utf-8") as f:
                try:
                    content = await f.read()
                    return json.loads(content) if content else {}
                except json.JSONDecodeError:
                    return {} 
        return {}

    async def save_badge_data(self, data):
        """Асинхронно сохраняет данные в JSON, обновляя только изменённые ключи"""
        async with aiofiles.open(BADGE_STATUS, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, indent=4, ensure_ascii=False))

    @Base.retry
    @open_session
    async def start_parse_badges_stats(self):
        status, user_info = await self.get_user_info()
        
        if not status or not user_info:
            return False

        user_data = user_info.get("user", {})
        badges = user_data.get("badges", [])
        total_xp = user_data.get("totalExperiencePoints", 0)

        # Подсчёт склеймленных бейджей
        claimed_badges = sum(1 for badge in badges if badge.get("claimed"))

        # Формируем список бейджей
        badges_info = {
            badge["badge"]["name"]: badge["claimed"]
            for badge in badges
        }

        # Парсинг токенов
        status, token_list = await self.get_all_token_balances()
        tokens_info = {}
        
        if status and token_list:
            for token_data in token_list:
                token_symbol = token_data["symbol"]
                balance = TokenAmount(
                    amount=int(token_data["balance"]["raw"]),
                    decimals=int(token_data["decimals"]),
                    wei=True
                )
                tokens_info[token_symbol] = float(balance.Ether)

        # Итоговая структура для записи
        stats = {
            "database_index": self.data.id,
            "wallet": self.data.evm_address,
            "total_xp": total_xp,
            "available_badges": len(badges),
            "claimed_badges": claimed_badges,
            "badges": badges_info,
            "tokens": tokens_info  # Добавляем токены в stats
        }

        self.data.claimed_badges = claimed_badges
        self.data.badges_parse_finished = True
    
        async with tasks_lock:
            # Загружаем существующие данные
            existing_data = await self.load_badge_data()

            # Обновляем или добавляем запись
            existing_data[self.data.evm_address] = stats

            # Записываем обратно в файл
            await self.save_badge_data(existing_data)

            # Записываем в базу
            await self.write_to_db()

        logger.success(f'[{self.data.id}] | {self.data.evm_address} | badges stats и токены успешно спаршены! Сlaimed badges: {claimed_badges}, Токенов: {len(tokens_info)}')
        return True

    async def get_voted_apps(self):

        response = await self.async_session.get(
            f'https://backend.portal.abs.xyz/api/user/{self.data.abstract_smartwallet.lower()}/votes',
            headers=self.get_abs_portal_base_headers()
        )

        if not response.status_code:
            logger.error(f'[{self.data.id}] | {self.data.evm_address} | не смог получить votes. Status code: {response.status_code} | Ответ сервера: {response.text}')
            return False, []
        
        voted_apps = response.json().get('votedApps', [])
        return True, voted_apps

    async def get_all_apps_list(self):
        page = 1
        all_apps = []
        
        while True:
            response = await self.async_session.get(
                f"https://backend.portal.abs.xyz/api/app?page=${page}&limit=20&category=",
                headers=self.get_abs_portal_base_headers()
            )
            if response.status_code != 200:
                logger.error(f'[{self.data.id}] | {self.data.evm_address} | не смог получить all apps list. Status code: {response.status_code} | Ответ сервера: {response.text}')
                return False, []

            data = response.json()
            
            apps = [{"id": item["id"], "name": item["name"]} for item in data["items"]]
            all_apps.extend(apps)
            
            if data["pagination"]["totalPages"] == page:
                break
            page += 1
        
        return True, all_apps
    
    @Base.retry
    @open_session
    async def start_vote(self):

        smart_wallet_balance = await self.check_smart_wallet_balance()
        if float(smart_wallet_balance.Ether) < MIN_BALANCE:
            logger.error(
                f'[{self.data.id}] | {self.data.evm_address} | баланс smart wallet меньше MIN_BALANCE. '
                f'Vote не возможен. Smart wallet balance: {smart_wallet_balance.Ether} | MIN_BALANCE: {MIN_BALANCE}'
            )
            return True

        status, voted_apps = await self.get_voted_apps()
        if not status:
            return False

        status, all_apps = await self.get_all_apps_list()
        if not status:
            return False
        
        if voted_apps:
            logger.info(f'[{self.data.id}] | {self.data.evm_address} | уже успешно проголосовал за {voted_apps}')

        all_apps = [app for app in all_apps if int(app["id"]) not in set(voted_apps)]

        if not all_apps:
            logger.warning(f'[{self.data.id}] | {self.data.evm_address} | нет доступных app для vote')
            return True
        
        random_app = random.choice(all_apps)
        
        logger.info(f'[{self.data.id}] | {self.data.evm_address} | start voting for APP: {random_app['name']} | ID: {random_app['id']}')

        vote_contract = self.eth_client.w3.eth.contract(address=VOTE_CONTRACT, abi=json.load(open(VOTE_ABI)))
        encoded_data = vote_contract.encodeABI(
            fn_name="voteForApp",
            args=[int(random_app['id'])]
        )

        transaction = {
            "chain": Networks.Abstract.chain_id,
            "from": self.data.abstract_smartwallet,
            "to": VOTE_CONTRACT,
            "data": encoded_data,
            "value": 0
        }

        status, msg = await self.eth_client.send_abstract_tx(self.async_session, self.data, transaction)
        if not status:
            logger.error(f'[{self.data.id}] | {self.data.evm_address} | {msg}')
            return False
        
        logger.success(f"[{self.data.id}] | {self.data.evm_address} | Транзакция успешно выполнена! Хэш: {Networks.Abstract.explorer}{msg}")
        await asyncio.sleep(5)
        status, check_voted_apps = await self.get_voted_apps()
        if not status:
            return False
        
        if len(check_voted_apps) > len(voted_apps):
            self.data.abstract_vote = True
            async with tasks_lock:
                await self.write_to_db()
            logger.success(f"[{self.data.id}] | {self.data.evm_address} | успешно проголосовал за APP: {random_app['name']} | ID: {random_app['id']}")
            return True

        logger.error(f"[{self.data.id}] | {self.data.evm_address} | возника проблема с проверкой voted apps. До транзакции: {len(voted_apps)} - {voted_apps} | После транзакции: {len(check_voted_apps)} - {check_voted_apps}. Состояние не изменилось!")
        return False
    
    async def get_all_token_balances(self):
        response = await self.async_session.get(
            f'https://backend.portal.abs.xyz/api/user/{self.data.abstract_smartwallet}/wallet/balances',
            headers=self.get_abs_portal_base_headers(),
        )

        if response.status_code == 200:
            return True, response.json().get('tokens', [])
        logger.error(f'[{self.data.id}] | {self.data.evm_address} | не смог спарсить баланс всех токенов. Status code: {response.status_code} | Ответ сервера: {response.text}')
        return False, ''
    

    async def get_token_with_max_balance(self):

        status, token_list = await self.get_all_token_balances()
        if not status:
            return status, token_list
        
        if not token_list:
            logger.error(f'[{self.data.id}] | {self.data.evm_address} | не токенов на смарт-контракте {self.data.abstract_smartwallet} который прикреплен к кошельку')

        tokens = []
        
        for token_data in token_list:
            if token_data['symbol'] not in SWAP_TOKENS:
                continue
                
            if SWAP_ONLY_TOKEN_TO_ETH and token_data['symbol'] == "ETH":
                continue

            balance = TokenAmount(
                amount=int(token_data["balance"]["raw"]),
                decimals=int(token_data["decimals"]),
                wei=True
            )

            token = Token(
                name=token_data["name"],
                symbol=token_data["symbol"],
                contract_address=token_data["contract"],
                decimals=int(token_data["decimals"]),
                balance=balance,
                usd_price=float(token_data.get("usdPrice", 0.0)),
                usd_value=float(token_data.get("usdValue", 0.0)),
            )

            tokens.append(token)

            logger.info(
                f'[{self.data.id}] | {self.data.evm_address} | Токен: {token.name} ({token.symbol}), '
                f'Баланс: {token.balance.Ether} {token.symbol}, Цена: {token.usd_price} USD, Стоимость: {token.usd_value} USD'
            )

        non_zero_tokens = [token for token in tokens if token.usd_value > 0]

        if not non_zero_tokens:
            logger.error(f'[{self.data.id}] | {self.data.evm_address} | все токены имеют нулевой баланс')
            return False, None

        max_balance_token = max(non_zero_tokens, key=lambda t: t.usd_value)

        return True, max_balance_token

    async def prepare_quote(self, json_data):
        headers = {
            'accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://relay.link',
            'priority': 'u=1, i',
            'sec-ch-ua': f'"Google Chrome";v="{self.version}", "Chromium";v="{self.version}", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': f'"{self.platform}"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': self.data.user_agent,
        }
        
        json_data['amount'] = str(json_data['amount'])

        response = await self.async_session.post(
            'https://api.relay.link/quote', 
            headers=headers, 
            json=json_data
        )

        if response.status_code == 200:
            answer = response.json()
            percent_value = abs(float(answer.get("details", {}).get("totalImpact", {}).get("percent", None)))
            if percent_value > ABS_SWAP_SLIPPAGE / 100:
                logger.error(f'{self.data.id} | {self.data.evm_address} | текущий slippage для swap в {Networks.Abstract.name} составит {percent_value}%. Что больше заданого в настройках {ABS_SWAP_SLIPPAGE / 100}')
                return False, None
            return True, answer
        logger.error(f'[{self.data.id}] | {self.data.evm_address} | Не смог создать abstract swap quote | код ответа сервера - {response.status_code}. Ответ сервера: {response.text}')
        return False, None

    @Base.retry
    @open_session
    async def start_swap(self):

        smart_wallet_balance = await self.check_smart_wallet_balance()
        if float(smart_wallet_balance.Ether) < MIN_BALANCE:
            logger.error(
                f'[{self.data.id}] | {self.data.evm_address} | баланс smart wallet меньше MIN_BALANCE. '
                f'Cвап не возможен. Smart wallet balance: {smart_wallet_balance.Ether} | MIN_BALANCE: {MIN_BALANCE}'
            )
            return True

        status: bool
        token: Token

        status, token = await self.get_token_with_max_balance()
        if not status:
            return True
    
        logger.info(
            f'[{self.data.id}] | {self.data.evm_address} | Токен с наибольшим балансом: {token.name} ({token.symbol}), '
            f'Баланс: {token.balance.Ether} {token.symbol} | Стоимость: {token.usd_value} USD'
        )

        if token.usd_value < MIN_TOKEN_SWAP_USD_VALUE:
            logger.error(f'[{self.data.id}] | {self.data.evm_address} | MIN_TOKEN_SWAP_USD_VALUE должно быть больше {MIN_TOKEN_SWAP_USD_VALUE}. Текущий Value: {token.usd_value}')
            return True

        if token.symbol != 'ETH':
            swap_to_symbol = 'ETH'
            swap_to = SWAP_TOKENS['ETH']
        else:
            swap_to_symbol = secrets.choice(ETH_SWAP_TO)
            swap_to = SWAP_TOKENS[swap_to_symbol]

        if USE_STATIC_AMOUNT:
            if token.symbol != 'ETH':
                get_swap_amount = token.balance
                logger.info(f'[{self.data.id}] | {self.data.evm_address} | начинаю свап {get_swap_amount.Ether} {token.symbol} на {swap_to_symbol}')
            else:
                get_swap_amount = TokenAmount(get_amount(NATIVE_ETH_TO_SWAP, 18))
                logger.info(f'[{self.data.id}] | {self.data.evm_address} | начинаю свап {get_swap_amount.Ether} {token.symbol} на {swap_to_symbol}')
        else:
            if token.symbol != 'ETH':
                get_swap_amount = token.balance
                logger.info(f'[{self.data.id}] | {self.data.evm_address} | начинаю свап {get_swap_amount.Ether} {token.symbol} (100%) на {swap_to_symbol}')
            else:
                percent_eth_to_swap = secrets.randbelow(
                    PERCENT_NATIVE_TO_TX[1] - PERCENT_NATIVE_TO_TX[0] + 1
                ) + PERCENT_NATIVE_TO_TX[0]
                get_swap_amount = TokenAmount(int((token.balance.Wei / 100) * percent_eth_to_swap), decimals=18, wei=True)
                logger.info(f'[{self.data.id}] | {self.data.evm_address} | начинаю свап {get_swap_amount.Ether} {token.symbol} ({percent_eth_to_swap}%) на {swap_to_symbol}')

        if token.symbol == 'ETH':
            if float(token.balance.Ether) <= float(get_swap_amount.Ether) + MIN_BALANCE:
                logger.error(
                    f'[{self.data.id}] | {self.data.evm_address} | недостаточно баланса {Networks.Abstract.coin_symbol}. '
                    f'Необходимо для свапа {get_swap_amount.Ether} {Networks.Abstract.coin_symbol} '
                    f'+ комиссия. Текущий баланс: {token.balance.Ether} {Networks.Abstract.coin_symbol}.'
                )
                return True

        if token.symbol != 'ETH':
            balance_before_swap = await self.check_smart_wallet_balance()
        else:
            erc20_contract = self.eth_client.w3.eth.contract(address=self.eth_client.w3.to_checksum_address(swap_to), abi=DefaultABIs.Token)
            balance_before_swap = await erc20_contract.functions.balanceOf(self.eth_client.w3.to_checksum_address(self.data.abstract_smartwallet)).call()
    
        swap_data = {
            'user': self.data.abstract_smartwallet,
            'destinationCurrency': swap_to,
            'destinationChainId': Networks.Abstract.chain_id,
            'originCurrency': token.contract_address,
            'originChainId': Networks.Abstract.chain_id,
            'amount': get_swap_amount.Wei,
            'recipient': self.data.abstract_smartwallet,
            'tradeType': "EXACT_INPUT",
            'referrer': "abstract",
            'slippageTolerance': str(ABS_SWAP_SLIPPAGE),
        }

        status, tx_data = await self.prepare_quote(swap_data)
        if not status:
            return False
        
        tx_steps = tx_data.get('steps', [])

        if not tx_steps:
            logger.error(f'[{self.data.id}] | {self.data.evm_address} | ошибка получен пустой tx_steps')
            return False

        for num, tx in enumerate(tx_steps, start=1):

            tx_steps = tx
            data = tx_steps.get('items', [{}])
            if isinstance(data, list) and data:
                data = data[0].get('data', {})
            else:
                logger.error(f'[{self.data.id}] | {self.data.evm_address} | tx_data пустая или другая структура: {tx_steps}!')
                return False
            
            transaction = {
                "chain": data['chainId'],
                "from": data['from'],
                "to": data['to'],
                "data": data['data'],
                "value": int(data['value'])
            }

            status, msg = await self.eth_client.send_abstract_tx(self.async_session, self.data, transaction, swap=True)
            if not status:
                logger.error(f'[{self.data.id}] | {self.data.evm_address} | {msg}')
                return False
            
            logger.success(f"[{self.data.id}] | {self.data.evm_address} | Транзакция успешно выполнена! Хэш: {Networks.Abstract.explorer}{msg}")

            if num == 1:
                sleep_time = random.randint(5, 20)
                logger.success(f"[{self.data.id}] | {self.data.evm_address} | cон {sleep_time} секунд после успешного действия...")
                await asyncio.sleep(sleep_time)
        
        if token.symbol != 'ETH':
            balance_after_swap = await self.check_smart_wallet_balance()
            balance_difference = TokenAmount(
                amount=abs(balance_before_swap.Wei - balance_after_swap.Wei), 
                wei=True
            )
        else:
            balance_after_swap = await erc20_contract.functions.balanceOf(self.eth_client.w3.to_checksum_address(self.data.abstract_smartwallet)).call()
            balance_difference = TokenAmount(
                amount=abs(balance_before_swap - balance_after_swap), 
                decimals=(await erc20_contract.functions.decimals().call()),
                wei=True
            )

        day = random.randint(NEXT_SWAP_AFTER_DAYS[0], NEXT_SWAP_AFTER_DAYS[1])
        self.data.abstract_swap = datetime.now(timezone.utc) + timedelta(days=day)
        async with tasks_lock:
            await self.write_to_db()
        
            logger.success(
                f'[{self.data.id}] | {self.data.evm_address} | свап успешно завершен. Получено {balance_difference.Ether} '
                f'{swap_to_symbol}. Cледующий свап будет возможен следующий свап будет возможен после {str(self.data.abstract_swap)} UTC'
            )

        return True