import json
import asyncio
import traceback


from playwright.async_api import async_playwright, TimeoutError
from playwright._impl._api_structures import ProxySettings
from sqlalchemy.ext.asyncio import AsyncSession


from data.config import logger, METAMASK
from settings.settings import NUMBER_OF_ATTEMPTS
from db_api.database import Accounts, db
from utils.encrypt_params import get_private_key


class PlaywrightCompleter:
    def __init__(self, data: Accounts):
        self.data = data
        self.proxy = ProxySettings(self.setup_proxy(data.proxy))
        self.version = self.data.user_agent.split('Chrome/')[1].split('.')[0]
        self.yellow = None

    @staticmethod
    def setup_proxy(proxy):
        username_password, server_port = proxy.replace('http://', '').split('@')
        username, password = username_password.split(':')
        server, port = server_port.split(':')
        proxy = {
            "server": f"http://{server}:{port}",
            "username": username,
            "password": password,
        }
        return proxy
    
    async def metamask_login(self, browser):
        for _ in range(60):
            if len(browser.pages) > 1:
                # Ищем страницу с MetaMask
                metamask_page = None
                for pg in browser.pages:
                    title = await pg.title()
                    if "MetaMask" in title:
                        metamask_page = pg
                        break
                if metamask_page:
                    logger.info(f"[{self.data.id}] | {self.data.evm_address} |Вкладка MetaMask найдена!")
                    break
            await asyncio.sleep(1)
        else:
            logger.error(f"[{self.data.id}] | {self.data.evm_address} | Вкладка MetaMask так и не появилась.")
            await browser.close()
            return False, '', ''

        page = metamask_page
        logger.info(f"[{self.data.id}] | {self.data.evm_address} | Переключились на вкладку MetaMask с URL: {page.url}")

        await page.wait_for_load_state('domcontentloaded', timeout=60000)

        # Инициализация MetaMask
        await page.locator("input#onboarding__terms-checkbox").wait_for(state="visible", timeout=60000)
        await page.click("input#onboarding__terms-checkbox")
        await page.locator("button[data-testid='onboarding-create-wallet']").wait_for(state="visible", timeout=60000)
        await page.click("button[data-testid='onboarding-create-wallet']")

        await page.locator("button[data-testid='metametrics-no-thanks']").wait_for(state="visible", timeout=60000)
        await page.click("button[data-testid='metametrics-no-thanks']")

        await page.locator("input[data-testid='create-password-new']").wait_for(state="visible", timeout=60000)
        await page.fill("input[data-testid='create-password-new']", "123456--")
        await page.locator("input[data-testid='create-password-confirm']").wait_for(state="visible", timeout=60000)
        await page.fill("input[data-testid='create-password-confirm']", "123456--")
        await page.locator("input[data-testid='create-password-terms']").wait_for(state="visible", timeout=60000)
        await page.click("input[data-testid='create-password-terms']")
        await page.locator("button[data-testid='create-password-wallet']").wait_for(state="visible", timeout=60000)
        await page.click("button[data-testid='create-password-wallet']")

        await page.locator("button[data-testid='secure-wallet-later']").wait_for(state="visible", timeout=60000)
        await page.click("button[data-testid='secure-wallet-later']")

        await page.locator("input[data-testid='skip-srp-backup-popover-checkbox']").wait_for(state="visible", timeout=60000)
        await page.click("input[data-testid='skip-srp-backup-popover-checkbox']")
        await page.locator("button[data-testid='skip-srp-backup']").wait_for(state="visible", timeout=60000)
        await page.click("button[data-testid='skip-srp-backup']")

        await page.locator("button[data-testid='onboarding-complete-done']").wait_for(state="visible", timeout=60000)
        await page.click("button[data-testid='onboarding-complete-done']")

        await page.locator("button[data-testid='pin-extension-next']").wait_for(state="visible", timeout=60000)
        await page.click("button[data-testid='pin-extension-next']")

        await page.locator("button[data-testid='pin-extension-done']").wait_for(state="visible", timeout=60000)
        await page.click("button[data-testid='pin-extension-done']")

        # Импорт аккаунта
        await page.locator("button[data-testid='account-menu-icon']").wait_for(state="visible", timeout=60000)
        await page.click("button[data-testid='account-menu-icon']")
        logger.info(f"[{self.data.id}] | {self.data.evm_address} | Открыли меню аккаунта.")

        await page.locator("button[data-testid='multichain-account-menu-popover-action-button']").wait_for(state="visible", timeout=60000)
        await page.click("button[data-testid='multichain-account-menu-popover-action-button']")
        logger.info(f"[{self.data.id}] | {self.data.evm_address} | Нажали 'Add account or hardware wallet'.")

        await page.locator("button[data-testid='multichain-account-menu-popover-add-imported-account']").wait_for(state="visible", timeout=60000)
        await page.click("button[data-testid='multichain-account-menu-popover-add-imported-account']")
        logger.info(f"[{self.data.id}] | {self.data.evm_address} | Нажали 'Import account'.")

        await page.locator("input#private-key-box").wait_for(state="visible", timeout=60000)
        await page.fill("input#private-key-box", get_private_key(self.data))
        logger.info(f"[{self.data.id}] | {self.data.evm_address} | Вставили приватный ключ.")

        import_button = page.locator("button[data-testid='import-account-confirm-button']")
        await import_button.wait_for(state="visible", timeout=60000)
        logger.info(f" [{self.data.id}] | {self.data.evm_address} | Ожидаем, пока кнопка 'Import' станет активной.")
        for _ in range(60):
            if await import_button.is_enabled():
                await import_button.click()
                logger.info(f"[{self.data.id}] | {self.data.evm_address} | Нажали 'Import'.")
                break
            await asyncio.sleep(1)

        return page
    
    async def login_abs_xyz(self, browser, page):

        # Переход на страницу ab
        url = 'https://www.abs.xyz/login'
        await page.goto(url)
        await page.wait_for_load_state('domcontentloaded')

        login_with_wallet_button = page.locator("button.styles_loginButton___pSyl", has_text="Login with Wallet")
        await login_with_wallet_button.wait_for(state="visible", timeout=60000)
        await login_with_wallet_button.click()
        logger.info(f"[{self.data.id}] | {self.data.evm_address} | Нажали 'Login with Wallet'.")

        metamask_button = page.locator("button.login-method-button", has_text="MetaMask")
        await metamask_button.wait_for(state="visible", timeout=60000)
        await metamask_button.click()
        logger.info(f"[{self.data.id}] | {self.data.evm_address} | Нажали 'MetaMask Connect'.")
        try:
            metamask_popup = await browser.wait_for_event("page", timeout=60000)

            if metamask_popup.is_closed():
                logger.error(f"[{self.data.id}] | {self.data.evm_address} | Окно MetaMask было закрыто прежде, чем мы смогли выполнить действия.")
                return False

            await metamask_popup.wait_for_load_state('domcontentloaded', timeout=60000)

            # Нажимаем "Подключиться"
            connect_button = metamask_popup.locator("button[data-testid='confirm-btn']")
            await connect_button.wait_for(state="visible", timeout=60000)
            await connect_button.click()
            logger.info(f"[{self.data.id}] | {self.data.evm_address} | Нажали 'Подключиться'.")

            # Нажимаем "Подтвердить"
            confirm_button = metamask_popup.locator("button[data-testid='confirm-footer-button']")
            await confirm_button.wait_for(state="visible", timeout=60000)
            await confirm_button.click()
            logger.info(f"[{self.data.id}] | {self.data.evm_address} | Нажали 'Подтвердить'.")

        except TimeoutError:
            logger.error(f"[{self.data.id}] | {self.data.evm_address} | Окно MetaMask для подтверждения или нужные элементы не появились вовремя.")
            return False
        except Exception as e:
            # Проверяем является ли это ошибкой закрытия окна
            if "Target page, context or browser has been closed" in str(e):
                logger.info(f"[{self.data.id}] | {self.data.evm_address} | Окно MetaMask закрылось после подтверждения — это ожидаемое поведение.")
                return False
            else:
                logger.error(f"[{self.data.id}] | {self.data.evm_address} | Неожиданная ошибка при работе с окном MetaMask: {e}")
                return False
            
        return True

    async def start_register(self):
        async with async_playwright() as p:
            for num, _ in enumerate(range(NUMBER_OF_ATTEMPTS), start=1):
                logger.info(f'[{self.data.id}] | {self.data.evm_address} | Попытка {num}/{NUMBER_OF_ATTEMPTS} в PW')
                try:
                    browser = await p.chromium.launch_persistent_context(
                        user_data_dir='',
                        headless=True,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                        ],
                        user_agent=self.data.user_agent,
                        proxy=self.proxy
                    )
                    
                    await browser.grant_permissions(["clipboard-read", "clipboard-write"])
                    await browser.add_cookies(json.loads(self.data.abstract_pw_cookies))
                    try:
                        page = browser.pages[-1]
                        url = 'https://www.abs.xyz/wallet'
                        await page.goto(url)
                        
                        await page.evaluate(f"(data) => {{ const obj = JSON.parse(data); for (const key in obj) localStorage.setItem(key, obj[key]); }}", self.data.abstract_pw_storage)
                        await asyncio.sleep(5)
                        await page.goto(url)
                        
                        try:
                            skip_button = page.locator("button.styles_container__P6k6P.styles_height-40__gnlvW.styles_secondary__O5bBD", has_text="Skip")
                            await skip_button.wait_for(state="visible", timeout=10000)
                            await skip_button.click()
                            logger.info(f"[{self.data.id}] | {self.data.evm_address} | Нажали 'Skip'.")
                        except TimeoutError:
                            logger.warning(f"[{self.data.id}] | {self.data.evm_address} | Кнопка 'Skip' так и не появилась.")

                        # Скопировать Smart Wallet
                        try:
                            # Нажимаем на кнопку "Copy" (инициируем копирование)
                            smart_wallet_button = page.locator("div.styles_copyButton__vBGJ1")
                            await smart_wallet_button.wait_for(state="visible", timeout=60000)
                            await smart_wallet_button.click()
                            logger.info(f"[{self.data.id}] | {self.data.evm_address} | Нажали 'Copy' для Smart Wallet.")

                            # Обрабатываем всплывающее окно с кнопкой "I understand"
                            i_understand_button = page.locator("button.styles_button__wCpbD.styles_container__P6k6P.styles_height-36__LM_wH.styles_primary__223tq", has_text="I understand")
                            if await i_understand_button.is_visible():
                                await i_understand_button.click()
                                logger.info(f"[{self.data.id}] | {self.data.evm_address} | Нажали 'I understand'.")
                            else:
                                logger.info(f"[{self.data.id}] | {self.data.evm_address} | Окно с 'I understand' не появилось, пропускаем.")

                            # Читаем Smart Wallet из буфера обмена
                            smart_wallet = await page.evaluate("navigator.clipboard.readText()")
                            if smart_wallet:
                                logger.info(f"[{self.data.id}] | {self.data.evm_address} | Скопировали Smart Wallet: {smart_wallet}")
                            else:
                                logger.warning(f"[{self.data.id}] | {self.data.evm_address} | Буфер обмена пуст, возможно, копирование не сработало.")

                            await asyncio.sleep(5)

                        except Exception as e:
                            logger.error(f"[{self.data.id}] | {self.data.evm_address} | Ошибка: {str(e)}")
                            await browser.close()
                            return False, '', ''

                        # Нажать на Security
                        security_button = page.locator("div.styles_linkButton__GAIYi", has_text="Security")
                        await security_button.wait_for(state="visible", timeout=60000)
                        await security_button.click()
                        logger.info(f"[{self.data.id}] | {self.data.evm_address} | Нажали 'Security'.")

                        # Нажать на Export
                        export_button = page.locator("span.footnote-1", has_text="Export")
                        await export_button.wait_for(state="visible", timeout=60000)
                        await export_button.click()
                        logger.info(f"[{self.data.id}] | {self.data.evm_address} | Нажали 'Export'.")

                        # Нажать на 'Yes, export'
                        yes_export_button = page.locator("button.styles_primary__223tq", has_text="Yes, export")
                        await yes_export_button.wait_for(state="visible", timeout=60000)
                        await yes_export_button.click()
                        logger.info(f"[{self.data.id}] | {self.data.evm_address} | Нажали 'Yes, export'.")

                        # Выбираем именно тот iframe, который содержит "embedded-wallets/export" в URL
                        export_iframe = page.frame_locator("iframe[src*='embedded-wallets/export']")

                        # Ищем кнопку «Copy Key» внутри этого iframe
                        privy_pk_button = export_iframe.locator("button:has-text('Copy Key')")
                        await privy_pk_button.wait_for(state="visible", timeout=60000)
                        await privy_pk_button.click()

                        # Короткая задержка, чтобы копирование наверняка успело завершиться
                        await asyncio.sleep(1)

                        # Читаем из буфера
                        privy_pk = await page.evaluate("navigator.clipboard.readText()")
                        logger.info(f"[{self.data.id}] | {self.data.evm_address} | Скопировали Privy PK")

                        await browser.close()
                        return True, smart_wallet, privy_pk

                    except Exception as e:
                        logger.error(f"[{self.data.id}] | {self.data.evm_address} | Ошибка при настройке MetaMask: {e}")
                        await browser.close()
                        return False, '', ''

                except Exception as err:
                    # Логирование стека и переход к следующей попытке
                    await browser.close()
                    print(traceback.print_exc())
                    print(err)
                    return False, '', ''

    async def claim_badge(self, name):
        async with async_playwright() as p:
            for num, _ in enumerate(range(NUMBER_OF_ATTEMPTS), start=1):
                logger.info(f'[{self.data.id}] | {self.data.evm_address} | Попытка {num}/{NUMBER_OF_ATTEMPTS} в PW')
                try:
                    browser = await p.chromium.launch_persistent_context(
                        user_data_dir='',
                        headless=False,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                        ],
                        user_agent=self.data.user_agent,
                        proxy=self.proxy
                    )
                    
                    await browser.add_cookies(json.loads(self.data.abstract_pw_cookies))
                    try:
                        page = browser.pages[-1]
                        url = 'https://www.abs.xyz/wallet'
                        await page.goto(url)
                        
                        await page.evaluate(f"(data) => {{ const obj = JSON.parse(data); for (const key in obj) localStorage.setItem(key, obj[key]); }}", self.data.abstract_pw_storage)
                        await asyncio.sleep(5)
                        await page.goto(url)
                        
                        # Нажать на Security
                        rewards_button = page.locator("div.styles_linkButton__GAIYi", has_text="Rewards")
                        await rewards_button.wait_for(state="visible", timeout=60000)
                        await rewards_button.click()
                        logger.info(f"[{self.data.id}] | {self.data.evm_address} | Нажали 'Rewards'.")
                        
                        badge_button = page.locator(f'img[alt="{name} padlock"]')
                        await badge_button.wait_for(state="visible", timeout=60000)
                        await badge_button.click()  

                        сlaim_button = page.locator('button.styles_buttonClaim___tjQp', has_text="Claim Badge")
                        await сlaim_button.wait_for(state="visible", timeout=60000)
                        await сlaim_button.click()
                        logger.success(f"[{self.data.id}] | {self.data.evm_address} | Нажали 'Claim Badge'. Спим 15 секунд после нажатия")
                        
                        await asyncio.sleep(15)

                        await browser.close()
                        return True

                    except Exception as e:
                        logger.error(f"[{self.data.id}] | {self.data.evm_address} | Ошибка при настройке MetaMask: {e}")
                        await browser.close()
                        return False

                except Exception as err:
                    # Логирование стека и переход к следующей попытке
                    await browser.close()
                    print(traceback.print_exc())
                    print(err)
                    return False


    async def update_cookies(self):
        async with async_playwright() as p:
            for num, _ in enumerate(range(NUMBER_OF_ATTEMPTS), start=1):
                logger.info(f'[{self.data.id}] | {self.data.evm_address} | Попытка {num}/{NUMBER_OF_ATTEMPTS} обновить/создать куки в PW')
                try:
                    browser = await p.chromium.launch_persistent_context(
                        user_data_dir='',
                        headless=False,
                        args=[
                            f"--disable-extensions-except={METAMASK}",
                            f"--load-extension={METAMASK}",
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                        ],
                        user_agent=self.data.user_agent,
                        proxy=self.proxy
                    )
                    
                    await asyncio.sleep(5)
                    # Ожидаем появления вкладки MetaMask
                    logger.info(f"[{self.data.id}] | {self.data.evm_address} | Ожидаем появления вкладки MetaMask...")

                    try:
                        page = await self.metamask_login(browser=browser)
                        
                        for _ in range(3):
                            status = await self.login_abs_xyz(browser=browser, page=page)
                            if status:
                                break

                        try:
                            skip_button = page.locator("button.styles_container__P6k6P.styles_height-40__gnlvW.styles_secondary__O5bBD", has_text="Skip")
                            await skip_button.wait_for(state="visible", timeout=10000)
                            await skip_button.click()
                            logger.info(f"[{self.data.id}] | {self.data.evm_address} | Нажали 'Skip'.")
                        except TimeoutError:
                            logger.warning(f"[{self.data.id}] | {self.data.evm_address} | Кнопка 'Skip' так и не появилась.")

                        # Нажать на Security
                        security_button = page.locator("div.styles_linkButton__GAIYi", has_text="Security")
                        is_visible = await security_button.is_visible()
                        if not is_visible:
                            logger.error(f"[{self.data.id}] | {self.data.evm_address} | не смог авторизироваться. Проверьте прокси! Скорее всего 429 ошибка!")
                            return False, '', ''

                        cookies = await browser.cookies()
                        cookies_json = json.dumps(cookies)

                        local_storage = await page.evaluate("() => JSON.stringify(localStorage)")
                        
                        await browser.close()

                        if cookies_json and local_storage:
                            
                            return True, cookies_json, local_storage
                        
                        return False, '', ''

                    except Exception as e:
                        logger.error(f"[{self.data.id}] | {self.data.evm_address} | Ошибка при настройке MetaMask: {e}")
                        await browser.close()
                        return False, '', ''

                except Exception as err:
                    # Логирование стека и переход к следующей попытке
                    await browser.close()
                    print(traceback.print_exc())
                    print(err)
                    return False, '', ''

    async def write_to_db(self):
        async with AsyncSession(db.engine) as session:
            await session.merge(self.data)
            await session.commit()