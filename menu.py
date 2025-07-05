import os
import json
import asyncio
from rich.console import Console
from rich.prompt import Prompt, IntPrompt
from text import t
from loguru import logger
from config import save_config

console = Console()

def display_menu(config):
    os.system("cls" if os.name == "nt" else "clear")
    console.print("\n" + "="*40, style="bold cyan")
    console.print(f"          {t('menu.header', locale=config['language'])}", style="bold cyan")
    console.print("="*40, style="bold cyan")
    console.print(f"[bold cyan]{t('menu.title', locale=config['language'])}[/bold cyan]")
    console.print(t("menu.start_process", locale=config['language']))
    console.print(t("menu.change_language", locale=config['language']))
    console.print(t("menu.configure_settings", locale=config['language']))
    console.print(t("menu.exit", locale=config['language']))
    console.print()

def change_language(config):
    logger.info(t("log.changing_language", locale="en"))
    console.print(f"[bold cyan]{t('menu.select_language', locale=config['language'])}[/bold cyan]")
    console.print("[1] Русский")
    console.print("[2] English")
    console.print(f"{t('menu.back', locale=config['language'])}")
    choice = IntPrompt.ask(
        f"[cyan]{t('menu.select_language_option', locale=config['language'])}[/cyan]",
        choices=["0", "1", "2"]
    )
    if choice == 0:
        console.print(f"[yellow]{t('menu.back', locale=config['language'])}[/yellow]")
        return
    elif choice == 1:
        config['language'] = 'ru'
        console.print(f"[green]{t('menu.language_changed', locale=config['language'], language='Русский')}[/green]")
    elif choice == 2:
        config['language'] = 'en'
        console.print(f"[green]{t('menu.language_changed', locale=config['language'], language='English')}[/green]")
    save_config(config)
    logger.info(t("log.language_changed", locale="en", language=config['language']))

def configure_settings(config):
    logger.info(t("log.configuring_settings", locale="en"))
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        console.print(f"[bold cyan]{t('menu.configure_settings', locale=config['language'])}[/bold cyan]")
        console.print(f"[1] {t('menu.current_max_threads', locale=config['language'], value=config['max_threads'])}")
        console.print(f"{t('menu.back', locale=config['language'])}")
        choice = IntPrompt.ask(
            f"[cyan]{t('menu.select_setting_option', locale=config['language'])}[/cyan]",
            choices=["0", "1"]
        )
        if choice == 0:
            console.print(f"[yellow]{t('menu.back', locale=config['language'])}[/yellow]")
            break
        elif choice == 1:
            console.print(f"[cyan]{t('menu.current_max_threads', locale=config['language'], value=config['max_threads'])}[/cyan]")
            max_threads = IntPrompt.ask(
                f"[cyan]{t('menu.enter_max_threads', locale=config['language'])}[/cyan]",
                default=config['max_threads']
            )
            config['max_threads'] = max(1, max_threads)
            console.print(f"[green]{t('menu.max_threads_updated', locale=config['language'], value=config['max_threads'])}[/green]")
            save_config(config)
            logger.info(t("log.max_threads_updated", locale="en", value=config['max_threads']))
        input(t("menu.press_enter", locale=config['language']))

async def run_menu(config, run_process_func):
    while True:
        display_menu(config)
        choice = Prompt.ask(
            f"[bold cyan]{t('menu.select_option', locale=config['language'])}[/bold cyan]",
            choices=["1", "2", "3", "4"]
        )
        logger.info(t("log.option_selected", locale="en", choice=choice))
        if choice == "1":
            os.system("cls" if os.name == "nt" else "clear")
            await run_process_func(config)
        elif choice == "2":
            change_language(config)
        elif choice == "3":
            configure_settings(config)
        elif choice == "4":
            console.print(f"[cyan]{t('menu.goodbye', locale=config['language'])}[/cyan]")
            break
        input(t("menu.press_enter", locale=config['language']))