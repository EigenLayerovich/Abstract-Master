import inquirer
from termcolor import colored
from inquirer.themes import load_theme_from_dict as loadth


# MAIN MENU
def get_action() -> str:
    """Пользователь выбирает действие через меню"""

    theme = {
        'Question': {
            'brackets_color': 'bright_yellow'
        },
        'List': {
            'selection_color': 'bright_blue'
        },
    }

    question = [
        inquirer.List(
            "action",
            message=colored('Выберите ваше действие', 'light_yellow'),
            choices=[
                'Import data to db',
                'Abstract',
                'Exit'
            ]
        )
    ]

    return inquirer.prompt(question, theme=loadth(theme))['action']

 
def abstract_menu() -> str:
    """Меню для Sahara"""
    theme = {
        'Question': {
            'brackets_color': 'bright_yellow'
        },
        'List': {
            'selection_color': 'bright_blue'
        },
    }

    question = [
        inquirer.List(
            "swap_action",
            message=colored('Выберите действие для SaharaAI', 'light_yellow'),
            choices=[
                "🏆 Badges",
                "🔗 Onchain",
                "🔹 Register Accounts",
                "🐦 Connect Twitter",
                "👾 Connect Discord",
                "🌉 Bridge",
                "Exit"
            ]
        )
    ]

    return inquirer.prompt(question, theme=loadth(theme))['swap_action']


def bridge_menu() -> str:
    """Меню для Bridge"""
    theme = {
        'Question': {
            'brackets_color': 'bright_yellow'
        },
        'List': {
            'selection_color': 'bright_blue'
        },
    }

    question = [
        inquirer.List(
            "swap_action",
            message=colored('Выберите действие для Bridge', 'light_yellow'),
            choices=[
                "1) Relay",
                "Exit"
            ]
        )
    ]

    return inquirer.prompt(question, theme=loadth(theme))['swap_action']


def badges_menu() -> str:
    """Меню для badges_menu"""
    theme = {
        'Question': {
            'brackets_color': 'bright_yellow'
        },
        'List': {
            'selection_color': 'bright_blue'
        },
    }

    question = [
        inquirer.List(
            "swap_action",
            message=colored('Выберите действие для Badges', 'light_yellow'),
            choices=[
                "Mix claim all eligible badges",
                "Connect Discord",
                "Connect Twitter / X",
                "Fund Your Account",
                "App Voter",
                "The Trader",
                "Parse Badges Stats",
                "Exit"
            ]
        )
    ]

    return inquirer.prompt(question, theme=loadth(theme))['swap_action']


def onchain_menu() -> str:
    """Меню для onchain_menu"""
    theme = {
        'Question': {
            'brackets_color': 'bright_yellow'
        },
        'List': {
            'selection_color': 'bright_blue'
        },
    }

    question = [
        inquirer.List(
            "swap_action",
            message=colored('Выберите действие для Badges', 'light_yellow'),
            choices=[
                "Vote",
                "Swap",
                "Exit"
            ]
        )
    ]

    return inquirer.prompt(question, theme=loadth(theme))['swap_action']
