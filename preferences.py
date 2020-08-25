import login
from selenium import webdriver
import os

DROP_WORTH_BUYING = -.035
AMOUNT_TO_INVEST_PER_PURCHASE = 10000

# Use stock ratings and YTD to avoid buying bad stocks even if they meet requirements (BETA)
USE_STOCK_RATINGS = True

# Panic sell when a purchased stock has a severly negative return
PANIC_SELL = False
DROP_WORTH_SELLING = -0.08

MINIMUM_CASH = 20000

AUTO_RELOAD_ON_TIMEOUT = True  # Automatically reload page when getting a 504 error
UPDATE_MIN_DELAY = 25

use_virtual_display = False
ignore_if_market_open = False
destructive = True  # if True, will actually perform buy & sell operations

username, password = login.username, login.password


loginpage = 'https://accounts.marketwatch.com/login?target=https%3A%2F%2Fwww.marketwatch.com%2Fgame%2Fimsmartasf'
home = 'https://www.marketwatch.com/game/imsmartasf/'

# set driver_path to '' if driver in system PATH
driver_path = ''
driver_type = webdriver.Chrome

reboot_after_run = False
