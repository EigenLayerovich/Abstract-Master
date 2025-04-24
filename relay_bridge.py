import asyncio
from web3 import Web3

from settings.settings import RELAY_BRIDGE_NETWORK_APPLY, AMOUNT_TO_BRIDGE, DEPOSIT_ALL_BALANCE, MIN_AMOUNT_IN_NETWORK, MIN_AMOUNT_TO_BRIDGE, MAX_RELAY_SLIPPAGE
from data.models import Networks
from clients.eth.eth_client import EthClient
from data.config import logger
from utils.get_amount import get_amount
from data.models import TokenAmount
from tasks import Base
from utils.encrypt_params import get_private_key
from data.config import tasks_lock


class RelayBridge(Base):

    def __init__(self, data):
        super().__init__(data)

    async def check_balances(self):
        """
        Проверяет баланс на сетях, где в словаре relay_bridge_apply стоит True.
        Возвращает сеть и баланс с наибольшим значением.
        """
        max_balance: TokenAmount = TokenAmount(0)
        max_network: Networks | None = None

        for network_name, enabled in RELAY_BRIDGE_NETWORK_APPLY.items():
            if enabled:
                network: Networks = getattr(Networks, network_name, None)
                if network:
                    eth_client = EthClient(
                        private_key=get_private_key(self.data), 
                        network=network, 
                        user_agent=self.data.user_agent, 
                        proxy=self.data.proxy
                    )
                    if await eth_client.w3.is_connected():
                        balance = TokenAmount(await eth_client.w3.eth.get_balance(self.data.evm_address), wei=True)
                        logger.info(
                            f'[{self.data.id}] | {self.data.evm_address} | Проверка баланса EVM адреса '
                            f'в сети {network_name}: {balance.Ether} {network.coin_symbol}'
                        )
                        if balance.Wei > max_balance.Wei:
                            max_balance = balance
                            max_network = network
                    else:
                        logger.warning(f"{self.data.id} | {self.data.evm_address} | Не удалось подключиться к сети {network_name}")
                else:
                    logger.warning(f"{self.data.id} | {self.data.evm_address} | Сеть {network_name} не найдена в объекте Networks.")

        if max_network:
            logger.info(f"{self.data.id} | {self.data.evm_address} | Сеть с наибольшим балансом: {max_network.name}, Баланс: {max_balance.Ether} {network.coin_symbol}")
        return max_network, max_balance


    def get_headers(self, network):
        return {
            'accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://relay.link',
            'priority': 'u=1, i',
            'referer': f'https://relay.link/bridge/eclipse?fromChainId={network.chain_id}&fromCurrency=0x0000000000000000000000000000000000000000&toCurrency=0x0000000000000000000000000000000000000000',
            'sec-ch-ua': f'"Google Chrome";v="{self.version}", "Chromium";v="{self.version}", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': f'"{self.platform}"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': self.data.user_agent,
        }


    async def prepare_quote(self, network: Networks, amount: TokenAmount):

        json_data = {
            'user': self.data.evm_address,
            'originChainId': network.chain_id,
            'destinationChainId': 2741,
            'originCurrency': '0x0000000000000000000000000000000000000000',
            'destinationCurrency': '0x0000000000000000000000000000000000000000',
            'recipient': self.data.abstract_smartwallet,
            'tradeType': 'EXACT_INPUT',
            'amount': amount.Wei,
            'referrer': 'relay.link/swap',
            'useExternalLiquidity': False,
            'useDepositAddress': False,
            'slippageTolerance': str(MAX_RELAY_SLIPPAGE)
        }

        response = await self.async_session.post(
            'https://api.relay.link/quote', 
            headers=self.get_headers(network), 
            json=json_data
        )

        if response.status_code == 200:
            answer = response.json()
            percent_value = abs(float(answer.get("details", {}).get("totalImpact", {}).get("percent", None)))
            if percent_value > MAX_RELAY_SLIPPAGE / 100:
                logger.error(f'{self.data.id} | {self.data.evm_address} | текущий slippage для бриджа с {network.name} в abstract составит {percent_value}%. Что больше заданого в настройках {MAX_RELAY_SLIPPAGE / 100}')
                return False, None
            return True, answer
        logger.error(f'[{self.data.id}] | {self.data.evm_address} | Не смог создать quote | код ответа сервера - {response.status_code}. Ответ сервера: {response.text}')
        return False, None


    async def calculate_estimate_gas(self, tx_data, network):
        tx_info = tx_data['steps'][0]['items'][0]['data']
        eth_client = EthClient(
            private_key=get_private_key(self.data), 
            network=network, 
            user_agent=self.data.user_agent, 
            proxy=self.data.proxy
        )
        
        try:
            estimated_gas = await eth_client.w3.eth.estimate_gas({
                "from": Web3.to_checksum_address(tx_info['from']),
                "to": Web3.to_checksum_address(tx_info['to']),
                "data": tx_info['data'],
                "value": int(tx_info['value']),
                "chainId": tx_info['chainId']
            })
            return True, estimated_gas
        except Exception as e:
            logger.error(f"[{self.data.id}] | {self.data.evm_address} | Gas estimation failed: {e}")
            return False, 0 
        

    async def check_final_transaction_cost(self, tx_data, estimated_gas, network):
        """
        Проверяет окончательную стоимость транзакции на основе оценки газа и параметров сети.
        """
        tx_info = tx_data['steps'][0]['items'][0]['data']
        max_fee_per_gas = int(tx_info['maxFeePerGas'])
        max_priority_fee_per_gas = int(tx_info['maxPriorityFeePerGas'])
        
        # Получение baseFeePerGas из текущего блока
        eth_client = EthClient(
            private_key=get_private_key(self.data), 
            network=network, 
            user_agent=self.data.user_agent, 
            proxy=self.data.proxy
        )
        latest_block = await eth_client.w3.eth.get_block('latest')
        base_fee_per_gas = latest_block.get('baseFeePerGas', 0)

        # Расчет итоговой стоимости газа
        effective_gas_price = min(base_fee_per_gas + max_priority_fee_per_gas, max_fee_per_gas)
        total_gas_cost = TokenAmount(estimated_gas * effective_gas_price, wei=True)

        # logger.info(
        #     f"{self.data.sol_address} | Окончательная стоимость газа для транзакции: "
        #     f"{total_gas_cost.Ether} {network.coin_symbol}"
        # )
        return total_gas_cost
    

    async def send_transaction(self, tx_data, network, estimated_gas):
        """
        Отправляет транзакцию после проверки газа и готовности данных.
        Проверяет, что статус транзакции равен 1.
        """

        tx_info = tx_data['steps'][0]['items'][0]['data']
        eth_client = EthClient(
            private_key=get_private_key(self.data), 
            network=network, 
            user_agent=self.data.user_agent, 
            proxy=self.data.proxy
        )

        transaction = {
            "from": Web3.to_checksum_address(tx_info['from']),
            "to": Web3.to_checksum_address(tx_info['to']),
            "data": tx_info['data'],
            "value": int(tx_info['value']),
            "gas": estimated_gas,
            "maxFeePerGas": int(tx_info['maxFeePerGas']),
            "maxPriorityFeePerGas": int(tx_info['maxPriorityFeePerGas']),
            "nonce": await eth_client.w3.eth.get_transaction_count(eth_client.account.address),
            "chainId": tx_info['chainId'],
        }

        # Подпись транзакции
        signed_txn = eth_client.w3.eth.account.sign_transaction(transaction, get_private_key(self.data))

        try:
            # Отправка транзакции
            tx_hash = await eth_client.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            logger.info(f"[{self.data.id}] | {self.data.evm_address} | Транзакция отправлена! Ожидаю статус выполнения...")

            # Ожидание выполнения транзакции
            receipt = await eth_client.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Проверка статуса транзакции
            if receipt.status == 1:
                return True, tx_hash.hex()
            else:
                logger.warning(f"[{self.data.id}] | {self.data.evm_address} | Транзакция не выполнена (статус != 1). Хэш: {network.explorer}{tx_hash.hex()}")
                return False, None

        except Exception as e:
            logger.error(f"[{self.data.id}] | {self.data.evm_address} | Ошибка при отправке транзакции: {e}")
            return False, None
        

    async def check_bridge_status(self, tx_data, network):
        headers = self.get_headers(network)
        
        headers['referer'] = f'https://relay.link/bridge/eclipse?toCurrency=0x0000000000000000000000000000000000000000&fromChainId={network.chain_id}&fromCurrency=0x0000000000000000000000000000000000000000'

        response = await self.async_session.get(
            'https://api.relay.link/intents/status', 
            params={
                'requestId': tx_data['steps'][0]['requestId']
            },
            headers=self.get_headers(network)
        )

        if response.status_code == 200:
            answer = response.json().get('status')
            return True, answer
        logger.error(
            f'[{self.data.id}] | {self.data.evm_address} | Не смог проверить статус бриджа | '
            f'код ответа сервера - {response.status_code}. Ответ сервера: {response.text}'
        )
        return False, ''

    @Base.retry
    async def start_task(self):

        logger.info(f'[{self.data.id}] | {self.data.evm_address} | Начинаю бридж в сеть abstract...')

        network, balance = await self.check_balances()

        if not network and not balance.Ether:
            logger.error(f'[{self.data.id}] | {self.data.evm_address} | EVM адрес не имеет баланса в ETH необходимых сетях')
            return True
        
        if DEPOSIT_ALL_BALANCE:
            min_amount = TokenAmount(get_amount(MIN_AMOUNT_IN_NETWORK, 9))
            get_final_bridge_amount = TokenAmount(balance.Ether - min_amount.Ether)

            if get_final_bridge_amount.Ether < MIN_AMOUNT_TO_BRIDGE:
                logger.warning(
                    f'[{self.data.id}] | {self.data.evm_address} | Баланса EVM адреса '
                    f' в сети {network.name} недостаточно для бриджа. Текущий баланс {balance.Ether}. '
                    f'Для бриджа необходимо {min_amount.Ether} {network.coin_symbol} + комиссия за транзакцию!'
                )
                return True
        else:
            get_final_bridge_amount = TokenAmount(get_amount(AMOUNT_TO_BRIDGE, 9))
    
            if float(balance.Wei <= get_final_bridge_amount.Wei):
                logger.warning(
                     f'[{self.data.id}] | {self.data.evm_address} | Баланса EVM адреса '
                    f' в сети {network.name} недостаточно для бриджа. Текущий баланс {balance.Ether}. '
                    f'Для бриджа необходимо {get_final_bridge_amount.Ether} {network.coin_symbol} + комиссия за транзакцию!'
                )
                return True
            
        status, tx_data = await self.prepare_quote(network, get_final_bridge_amount)
        if not status:
            return True
    
        if status:
            status, estimated_gas = await self.calculate_estimate_gas(tx_data, network)
            if status:
                total_gas_cost = await self.check_final_transaction_cost(tx_data, estimated_gas, network)
                if total_gas_cost.Wei + get_final_bridge_amount.Wei > balance.Wei:
                    logger.info(
                        f'[{self.data.id}] | {self.data.evm_address} Недостаточно {network.coin_symbol} для бриджа '
                        f'и для оплаты комиссии за транзакцию. Необходимо {total_gas_cost.Ether + get_final_bridge_amount.Ether} {network.coin_symbol}. '
                        f'Текущий баланс: {balance.Ether} {network.coin_symbol}'   
                    )
                    return True

                # Отправка транзакции
                abstact_client = EthClient(
                    private_key=get_private_key(self.data),
                    network=Networks.Abstract,
                    user_agent=self.data.user_agent, 
                    proxy=self.data.proxy
                )
                native_balance_before_brige = TokenAmount(await abstact_client.w3.eth.get_balance(self.data.abstract_smartwallet), wei=True)
                status, tx_hash = await self.send_transaction(tx_data, network, estimated_gas)
                if status:
                    logger.success(f"[{self.data.id}] | {self.data.evm_address} | Транзакция успешно выполнена! Хэш: {network.explorer}{tx_hash}")
                    #logger.info(f'{self.data.sol_address} | Ожидаю завершения бриджа!')
                    while True:
                        status, answer = await self.check_bridge_status(tx_data, network)

                        if answer == 'success':
                            self.data.bridge_complete = True
                            async with tasks_lock:
                                await self.write_to_db()
                            native_balance_after_bridge = TokenAmount(await abstact_client.w3.eth.get_balance(self.data.abstract_smartwallet), wei=True)
                            balance_difference = abs(native_balance_before_brige.Ether - native_balance_after_bridge.Ether)
                            logger.success(f'[{self.data.id}] | {self.data.evm_address} | бридж успешно завершен... {balance_difference} ETH успешно забриджены в сеть Abstract на smartwallet {self.data.abstract_smartwallet}!')
                            return True

                        logger.info(f'[{self.data.id}] | {self.data.evm_address} | ожидаю успешного завершения бриджа...')
                        await asyncio.sleep(30)

        return False