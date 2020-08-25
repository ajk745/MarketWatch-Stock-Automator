from time import sleep
import json
import requests
import datetime
import traceback
import shelve
from datetime import date, timedelta
from preferences import *
import os
import csv
import sys
import bs4
from urllib.parse import urljoin


if use_virtual_display:
    from pyvirtualdisplay import Display
    display = Display(visible=0, size=(1000, 800))
    display.start()

# helper functions


def read_file(path):
    file = open(path)
    text = file.read()
    file.close()
    return text


def login():
    print('logging in')
    driver.get(loginpage)

    by_name('username').send_keys(username)
    by_name('password').send_keys(password)
    by_class('basic-login-submit').click()
    sleep(10)  # need to wait to make sure login properly works, 10 might be excessive


def buy_stock(name, amount, days):
    print('buying ' + str(amount) + '$ worth of ' + name)
    driver.get(home)

    # search interfeace
    by_class('j-miniTrade').send_keys(name)
    price = float(by_class('t-price').text)
    print('the price of ' + name + ' is:' + str(price))
    by_class('t-trade').click()

    # buy interface
    shares = int(amount / price)
    print('this equates to ' + str(shares) + ' shares')
    num_shares_elem = by_class('j-number-shares')
    num_shares_elem.clear()
    num_shares_elem.send_keys(shares)

    held_stocks = shelve.open(os.path.join('held_stocks', 'held_stocks'))
    sell_date = date.today() + timedelta(days)
    while sell_date.weekday() > 4:
        sell_date += timedelta(1)
    held_stocks[name] = {'buy_price': amount,
                         'sell_date': date.today() + timedelta(days), 'shares': shares}
    held_stocks.close()

    if destructive and (is_market_open() or ignore_if_market_open):
        by_class('j-submit').click()


def clean(text, num=False):
    result = str(text).replace('$', '').replace(',', '').replace('%', '')
    if num:
        try:
            return float(result)
        except:
            return 0
    else:
        return result


def get_webpage_element(page, selector):
    try:
        return page.select(selector)[0].text.strip()
    except:
        return ''


def get_stock_data(stock):  # Web Scraped because no free API :(
    data = {}
    link = 'https://financialmodelingprep.com/api/v3/quote/' + stock
    print("Getting stock data: " + stock)

    res = json.loads(requests.get(link).text)

    price = res[0]["price"]

    data['price'] = price

    data['prev_close'] = res[0]["previousClose"]
    data['open'] = res[0]["open"]
    data['PE'] = res[0]["pe"]
    data['EPS'] = res[0]["eps"]
    data['YTD'] = (price - res[0]["priceAvg200"]) / res[0]["priceAvg200"]

    return data


def get_cash_remaining():
    driver.get(home)

    elems = multiple_by_class('kv__primary')

    reserve = 0

    try:
        reserve = clean(elems[4].text, True)
    except:
        print("could not retrieve remaining cash")
        reserve = None

    return reserve


def get_sp_stock_data():
    print('getting current stock information for s&p 500 stocks')
    # get s&p stock list
    stock_info = {}

    f = open('stock_list.txt')

    names = []
    for line in f:
        names.append(line.strip())  # remove excess on ending
    f.close()

    for stock in names:
        try:
            data = get_stock_data(stock)
            stock_info[stock] = data
        except:
            f = open("errors.txt", "a")
            f.write(str(datetime.datetime.now()) +
                    '\n' + 'Error Getting Stock Data: ' + stock + '\n' + traceback.format_exc() + '\n\n')
            f.close()
            continue

    print('finished getting all stock info for s&p 500 - logged in stock_data.txt')

    data_log = open("stock_data.txt", "w")
    data_log.write(str(stock_info))
    data_log.close()
    return stock_info


def auto_buy(data):
    current = get_portfolio_stocks()
    cash_remaining = get_cash_remaining()
    stock_data = data
    for stock in stock_data.keys():
        price, prev_close, open_price, PE, EPS, YTD = data[stock]['price'], data[stock]['prev_close'], data[
            stock]['open'], data[stock]['PE'], data[stock]['EPS'], data[stock]['YTD']

        change = 0
        if not (prev_close == 0):
            change = (price - prev_close) / prev_close
        change_since_open = 0
        if not (open_price == 0):
            change_since_open = (price - open_price) / open_price
        print(stock, str(change), str(change_since_open), sep="    ")
        if change <= DROP_WORTH_BUYING and cash_remaining - AMOUNT_TO_INVEST_PER_PURCHASE >= MINIMUM_CASH and stock not in current:
            print('deciding whether to buy ' + stock +
                  ' because it dropped ' + str(change * 100) + '%')
            if YTD > 0.05 and cash_remaining - (AMOUNT_TO_INVEST_PER_PURCHASE * 2) >= MINIMUM_CASH:
                if change_since_open < -(DROP_WORTH_BUYING/2) and change_since_open > (DROP_WORTH_BUYING/2):
                    buy_stock(stock, (AMOUNT_TO_INVEST_PER_PURCHASE * 2), 2)
                    cash_remaining = get_cash_remaining()
                else:
                    buy_stock(stock, (AMOUNT_TO_INVEST_PER_PURCHASE * 2), 3)
                    cash_remaining = get_cash_remaining()
            elif YTD < -0.05:
                continue


def get_transaction_history():
    print('obtaining transaction history for previously purchased stocks')
    driver.get(home + 'portfolio')
    empty = True

    # switch tab to history
    driver.execute_script(
        "document.getElementsByClassName('label')[6].scrollIntoView()")
    by_class('j-tabItem').click()

    history = {}

    headers = ['Symbol', 'order time',
               'transaction time', 'type', 'amount', 'price']
    is_num = [False, False, False, False, True, True]

    def get_page():
        table = by_class('ranking')
        trs = table.find_elements_by_class_name(
            'table__row')[1:]  # first table row is headers

        for row in trs:
            tds = row.find_elements_by_class_name('table__cell')
            info = {}

            for i, td in enumerate(tds):
                if not td.text == '':
                    info[headers[i]] = clean(td.text, is_num[i])
                    empty = False
                else:
                    empty = True

            if not empty:
                name = info['Symbol']

                if name not in history and info['type'] == 'Buy':
                    history[name] = info

    transactions_title = multiple_by_class('title')[5]
    driver.execute_script("arguments[0].scrollIntoView();", transactions_title)
    sleep(10)

    # go through every page (table only shows 10 at a time)
    while True:
        get_page()
        # .find_element_by_tag_name('i')
        if not empty:
            next = multiple_by_class('j-next')[1]
            if next.get_attribute('data-is-disabled') == 'false':  # more to go
                next.click()
                sleep(3)
            else:
                break
        else:
            break

    return history

# def get_transaction_history_new(): # gets transaction history including only most recent buy for each stock if multiple entries appear
#    print('getting transaction history')
#    sleep(5)
#    driver.get(home + 'download?view=transactions&count=100000')
#    sleep(5)
#
#    address = downloads_folder + 'Portfolio Transactions - ' + market_watch_name + '.csv'
#
#    result = {}
#
#    with open(address) as csvfile:
#        reader = csv.DictReader(csvfile)
#        for row in reader:
#            name = row['Symbol']
#
#            if name not in result and row['Type'] == 'Buy':
#                row['Price'] = float(row['Price'].replace('$', ''))
#                result[name] = row
#
#    csvfile.close()
#
#    # delete the file
#    os.remove(address)
#
#    return result


def get_portfolio_stocks():
    print('checking prices of current stocks in portfolio')

    driver.get(urljoin(home, 'portfolio'))
    table = by_class('holdings')
    trs = table.find_elements_by_class_name(
        'table__row')[1:]  # first table row is headers

    portfolio = {}

    headers = ['name', 'shares', 'price', 'change',
               'change %', 'value', 'value change', 'value change %']

    for row in trs:
        tds = row.find_elements_by_class_name('table__cell')
        info = {}

        name = clean(tds[1].find_element_by_class_name('symbol').text)
        info['shares'] = int(clean(tds[1].find_element_by_class_name(
            'text').text.replace(' SHARES', ''), True))
        info['price'] = clean(
            tds[3].find_element_by_class_name('primary').text, True)
        info['price change'] = clean(
            tds[3].find_element_by_class_name('point').text, True)
        info['price change %'] = clean(
            tds[3].find_element_by_class_name('percent').text, True)
        info['value'] = clean(
            tds[4].find_element_by_class_name('primary').text, True)
        info['value change'] = clean(
            tds[4].find_element_by_class_name('point').text, True)
        info['value change %'] = clean(
            tds[4].find_element_by_class_name('percent').text, True)

        portfolio[name] = info

    return portfolio


def auto_sell(data):
    history = shelve.open(os.path.join('held_stocks', 'held_stocks'))
    current = get_portfolio_stocks()

    stock_data = data

    print(history)

    for key in current:
        try:
            old_price = history[key]['price']
            new_price = current[key]['price']
        except:
            continue

        change = (new_price - old_price) / old_price
        shares = history[key]['shares']

        # have to keep bond
        if date.today() == history[key]['sell_date'] and key != 'VGSH':
            del history[key]
            sell(key, shares)

        if PANIC_SELL and change < DROP_WORTH_SELLING:
            print('panic selling ' + key)
            del history[key]
            sell(key, shares)
    history.close()


def sell(name, shares):
    print('selling ' + str(shares) + ' of ' + name)
    driver.get(home + 'portfolio')

    # search interfeace
    by_class('j-miniTrade').send_keys(name)
    price = float(by_class('t-price').text)
    by_class('t-trade').click()

    # click sell
    header = by_class('lightbox__header')
    li = header.find_elements_by_class_name('radio__item')[2]
    label = li.find_element_by_class_name('label')
    label.click()

    # sell interface
    num_shares_elem = by_class('j-number-shares')
    num_shares_elem.clear()
    num_shares_elem.send_keys(shares)

    if destructive:
        by_class('j-submit').click()


def safe_exit():
    try:
        driver.close()
        driver.quit()
        print('sucessfully closed driver')
    except Exception:
        print('error when closing driver')
        pass

    try:
        display.stop()
        print('stopped display')
    except Exception:
        print('error stopping display')
        pass


def is_market_open():
    now = datetime.datetime.now()
    hour, minute = now.hour, now.minute

    return 9.5 <= hour + (minute / 60.0) and hour <= 15.5


def download_file_test():
    print('downloading sample file')
    driver.get(
        'https://www.marketwatch.com/game/ap-macro-4th-/download?view=transactions&count=100000')
#    driver.get(home + 'portfolio')

#    items = multiple_by_class('download__data')[2].click()
    sleep(30)
#    print(len(items))


while True:
    f = open("runhistory.txt", "w")

    try:
        if is_market_open() or ignore_if_market_open:  # if stock market open
            print('market is open or state ignored by preference, running algorithm')

#            chromeOptions = webdriver.ChromeOptions()
#            print(downloads_folder)
#            prefs = {"download.default_directory" : downloads_folder}
#            chromeOptions.add_experimental_option("prefs",prefs)

            # get stock data
            import ast
            # datafile = open('stock_data.txt').read()
            stock_data = get_sp_stock_data()

            # setup driver
            if driver_path != '':
                driver = driver_type(driver_path)
            else:
                driver = driver_type()

#            fp.set_preference("browser.download.folderList",2)
#            fp.set_preference("browser.download.manager.showWhenStarting",False)
#            fp.set_preference("browser.download.dir", os.getcwd())
#            fp.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/octet-stream")

            driver.implicitly_wait(100)

            by_name = driver.find_element_by_name
            by_class = driver.find_element_by_class_name
            by_selector = driver.find_element_by_css_selector

            multiple_by_class = driver.find_elements_by_class_name

            # MAIN OPERATIONS
            login()

            auto_buy(stock_data)
            auto_sell(stock_data)

            safe_exit()
        else:
            print('market is closed, algorithm will NOT run')

        print('sleeping for ' + str(UPDATE_MIN_DELAY) + ' minutes')
        sleep(UPDATE_MIN_DELAY * 60)  # sleep 30 minutes

    except Exception:
        print("Error Occured - Traceback Logged")

        f = open("errors.txt", "a")
        f.write(str(datetime.datetime.now()) +
                '\n' + traceback.format_exc() + '\n')
        f.close()

        safe_exit()
        print('Error Logged - Running again in ' + str(UPDATE_MIN_DELAY))
        sleep(UPDATE_MIN_DELAY)

    if reboot_after_run:
        os.system('sudo reboot now')
