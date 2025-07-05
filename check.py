import json
import os
import asyncio
import shutil
import random
from telethon import TelegramClient
from telethon.errors import FloodWaitError, AuthKeyUnregisteredError
from telethon.network import ConnectionTcpFull
from opentele.api import API
import socks
from rich.console import Console
from loguru import logger
from config import load_config
from menu import run_menu
from text import t

logger.remove()
logger.add("check.log", rotation="10 MB", format="{time:YYYY-MM-DD HH:mm:ss} - {level} - {message}")
logger.add(lambda msg: print(msg, end=""), colorize=True, format="{time:YYYY-MM-DD HH:mm:ss} - {level} - {message}")

console = Console()

sessions_dir = 'sessions'
unauthorized_sessions_dir = 'unauthorized_sessions'
json_dir = 'sessions'
proxy_file = 'proxy.txt'

running = False

def initialize_files_and_dirs(config):
    for directory in [sessions_dir, unauthorized_sessions_dir, json_dir]:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(t("log.dir_created", locale="en", dir=directory))
            console.print(f"[green]{t('menu.dir_created', locale=config['language'], dir=directory)}[/green]")
    if not os.path.exists(proxy_file):
        with open(proxy_file, 'w') as f:
            f.write("# Формат: host:port:username:password\n")
        logger.info(t("log.proxy_file_created", locale="en"))
        console.print(f"[green]{t('menu.proxy_file_created', locale=config['language'], file=proxy_file)}[/green]")

def load_proxies(config):
    initialize_files_and_dirs(config)
    proxies = []
    with open(proxy_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                parts = line.split(':')
                if len(parts) == 4:
                    host, port, username, password = parts
                    proxies.append((socks.SOCKS5, host, int(port), True, username, password))
                else:
                    logger.warning(t("log.invalid_proxy_format", locale="en", line=line))
    if not proxies:
        logger.error(t("log.proxy_file_empty", locale="en", file=proxy_file))
        console.print(f"[red]{t('menu.proxy_error', locale=config['language'], error=t('error.proxy_empty', locale=config['language']))}[/red]")
    return proxies

def load_auth_data(json_path, config, phone):
    if os.path.exists(json_path):
        with open(json_path, 'r') as f:
            auth_data = json.load(f)
        
        required_fields = ['app_id', 'app_hash', 'device', 'sdk', 'app_version', 'lang_pack', 'lang_code', 'system_lang_code']
        missing_fields = [field for field in required_fields if not auth_data.get(field)]
        if missing_fields:
            logger.info(t("log.api_data_missing_generating", locale="en", file=json_path))
            console.print(f"[yellow]{t('menu.api_data_missing_generating', locale=config['language'], file=json_path)}[/yellow]")
            api_data = API.TelegramDesktop.Generate(system="windows", unique_id=phone)
            auth_data['app_id'] = api_data.api_id
            auth_data['app_hash'] = api_data.api_hash
            auth_data['device'] = api_data.device_model
            auth_data['sdk'] = api_data.system_version
            auth_data['app_version'] = api_data.app_version
            auth_data['lang_pack'] = api_data.lang_pack
            auth_data['lang_code'] = api_data.lang_code
            auth_data['system_lang_code'] = api_data.system_lang_code
            with open(json_path, 'w') as f:
                json.dump(auth_data, f, indent=4)
            logger.info(t("log.api_data_generated", locale="en", file=json_path))
            console.print(f"[green]{t('menu.api_data_generated', locale=config['language'], file=json_path)}[/green]")
        return auth_data
    logger.info(t("log.auth_data_missing_creating", locale="en", file=json_path))
    console.print(f"[yellow]{t('menu.auth_data_missing_creating', locale=config['language'], file=json_path)}[/yellow]")
    
    api_data = API.TelegramDesktop.Generate(system="windows", unique_id=phone)
    default_auth_data = {
        "phone": phone,
        "session_file": phone,
        "app_id": api_data.api_id,
        "app_hash": api_data.api_hash,
        "device": api_data.device_model,
        "sdk": api_data.system_version,
        "app_version": api_data.app_version,
        "lang_pack": api_data.lang_pack,
        "lang_code": api_data.lang_code,
        "system_lang_code": api_data.system_lang_code
    }
    with open(json_path, 'w') as f:
        json.dump(default_auth_data, f, indent=4)
    logger.info(t("log.auth_data_created", locale="en", file=json_path))
    console.print(f"[green]{t('menu.auth_data_created', locale=config['language'], file=json_path)}[/green]")
    return default_auth_data

async def ensure_connected(client, phone, config):
    if not client.is_connected():
        try:
            await client.connect()
        except Exception as e:
            logger.error(t("log.connection_failed", locale="en", phone=phone, error=str(e)))
            console.print(f"[red]{t('menu.connection_failed', locale=config['language'], phone=phone, error=str(e))}[/red]")
            return False
    return True

async def process_session(json_file, proxies, semaphore, config):
    async with semaphore:
        phone = os.path.splitext(os.path.basename(json_file))[0]
        json_path = os.path.join(json_dir, f"{phone}.json")
        auth_data = load_auth_data(json_path, config, phone)
        if not auth_data:
            return False
        phone = auth_data.get('phone')
        if not phone:
            logger.error(t("log.phone_missing", locale="en", file=json_file))
            console.print(f"[red]{t('menu.phone_missing', locale=config['language'], file=json_file)}[/red]")
            return False
        session_file = os.path.join(sessions_dir, auth_data.get('session_file', phone))
        api_id = auth_data.get('app_id')
        api_hash = auth_data.get('app_hash')
        lang_pack = auth_data.get('lang_pack')
        lang_code = auth_data.get('lang_code')
        system_lang_code = auth_data.get('system_lang_code')
        device = auth_data.get('device')
        sdk = auth_data.get('sdk')
        app_version = auth_data.get('app_version')
        if not all([api_id, api_hash, lang_pack, lang_code, system_lang_code, device, sdk, app_version]):
            logger.error(t("log.api_data_missing", locale="en", file=json_file))
            console.print(f"[red]{t('menu.api_data_missing', locale=config['language'], file=json_file)}[/red]")
            return False
        if not os.path.exists(session_file + '.session'):
            logger.error(t("log.session_missing", locale="en", phone=phone))
            console.print(f"[red]{t('menu.session_missing', locale=config['language'], phone=phone)}[/red]")
            return False
        proxy = random.choice(proxies) if proxies else None
        if proxy:
            logger.info(t("log.using_proxy_old", locale="en", host=proxy[1], port=proxy[2]))
            console.print(f"[cyan]{t('menu.using_proxy_old', locale=config['language'], host=proxy[1], port=proxy[2])}[/cyan]")
        else:
            logger.info(t("log.no_proxy_old", locale="en", phone=phone))
            console.print(f"[cyan]{t('menu.no_proxy_old', locale=config['language'], phone=phone)}[/cyan]")
        client = TelegramClient(
            session=session_file,
            api_id=api_id,
            api_hash=api_hash,
            connection=ConnectionTcpFull,
            device_model=device,
            system_version=sdk,
            app_version=app_version,
            lang_code=lang_code,
            system_lang_code=system_lang_code,
            proxy=proxy
        )
        client._init_request.lang_pack = lang_pack
        try:
            if not await ensure_connected(client, phone, config):
                return False
            is_authorized = await client.is_user_authorized()
            if is_authorized:
                logger.info(t("log.session_authorized", locale="en", phone=phone))
                console.print(f"[green]{t('menu.session_authorized', locale=config['language'], phone=phone)}[/green]")
                return True
            else:
                logger.warning(t("log.session_not_authorized", locale="en", phone=phone))
                console.print(f"[yellow]{t('menu.session_not_authorized', locale=config['language'], phone=phone)}[/yellow]")
                unauthorized_session_path = os.path.join(unauthorized_sessions_dir, os.path.basename(session_file) + '.session')
                unauthorized_json_path = os.path.join(unauthorized_sessions_dir, os.path.basename(json_file))
                if os.path.exists(session_file + '.session'):
                    shutil.move(session_file + '.session', unauthorized_session_path)
                    logger.info(t("log.session_file_moved", locale="en", file=unauthorized_session_path))
                    console.print(f"[green]{t('menu.session_file_moved', locale=config['language'], file=unauthorized_session_path)}[/green]")
                if os.path.exists(json_path):
                    shutil.move(json_path, unauthorized_json_path)
                    logger.info(t("log.json_file_moved", locale="en", file=unauthorized_json_path))
                    console.print(f"[green]{t('menu.json_file_moved', locale=config['language'], file=unauthorized_json_path)}[/green]")
                return False
        except FloodWaitError as e:
            logger.error(t("log.flood_limit", locale="en", phone=phone, seconds=e.seconds))
            console.print(f"[red]{t('menu.flood_limit', locale=config['language'], phone=phone, seconds=e.seconds)}[/red]")
            return False
        except AuthKeyUnregisteredError:
            logger.error(t("log.session_unregistered", locale="en", phone=phone))
            console.print(f"[red]{t('menu.session_unregistered', locale=config['language'], phone=phone)}[/red]")
            unauthorized_session_path = os.path.join(unauthorized_sessions_dir, os.path.basename(session_file) + '.session')
            unauthorized_json_path = os.path.join(unauthorized_sessions_dir, os.path.basename(json_file))
            if os.path.exists(session_file + '.session'):
                shutil.move(session_file + '.session', unauthorized_session_path)
                logger.info(t("log.session_file_moved", locale="en", file=unauthorized_session_path))
                console.print(f"[green]{t('menu.session_file_moved', locale=config['language'], file=unauthorized_session_path)}[/green]")
            if os.path.exists(json_path):
                shutil.move(json_path, unauthorized_json_path)
                logger.info(t("log.json_file_moved", locale="en", file=unauthorized_json_path))
                console.print(f"[green]{t('menu.json_file_moved', locale=config['language'], file=unauthorized_json_path)}[/green]")
            return False
        except Exception as e:
            logger.error(t("log.session_error", locale="en", phone=phone, error=str(e)))
            console.print(f"[red]{t('menu.session_error', locale=config['language'], phone=phone, error=str(e))}[/red]")
            return False
        finally:
            if client.is_connected():
                await client.disconnect()

async def run_process(config):
    global running
    if running:
        console.print(f"[yellow]{t('menu.running', locale=config['language'])}[/yellow]")
        return
    running = True
    console.print(f"[green]{t('menu.starting_process', locale=config['language'])}[/green]")
    try:
        proxies = load_proxies(config)
        if not proxies:
            running = False
            return
        session_files = [f for f in os.listdir(sessions_dir) if f.endswith('.session')]
        json_files = []
        for session_file in session_files:
            phone = os.path.splitext(session_file)[0]
            json_path = os.path.join(json_dir, f"{phone}.json")
            load_auth_data(json_path, config, phone)
            json_files.append(json_path)
        if not json_files:
            console.print(f"[red]{t('menu.no_json_files', locale=config['language'], dir=json_dir)}[/red]")
            running = False
            return
        semaphore = asyncio.Semaphore(config['max_threads'])
        tasks = [process_session(json_file, proxies, semaphore, config) for json_file in json_files]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success = all(isinstance(result, bool) and result for result in results)
        if success:
            console.print(f"[green]{t('menu.process_completed', locale=config['language'])}[/green]")
        else:
            console.print(f"[yellow]{t('menu.process_failed', locale=config['language'])}[/yellow]")
    except Exception as e:
        console.print(f"[red]{t('menu.error', locale=config['language'], error=str(e))}[/red]")
    finally:
        running = False

async def main():
    config = load_config()
    await run_menu(config, run_process)

if __name__ == '__main__':
    asyncio.set_event_loop(asyncio.new_event_loop())
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except Exception as e:
        logger.error(t("log.main_error", locale="en", error=str(e)))
        console.print(f"[red]{t('menu.main_error', locale=load_config()['language'], error=str(e))}[/red]")
    finally:
        loop.close()