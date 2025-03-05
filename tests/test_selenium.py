#
# Copyright (c) 2023-2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import io
import os.path
import socket
import subprocess
import time

import pytest

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


data_dir = os.path.join(os.path.dirname(__file__), 'data')


@pytest.fixture(scope="session")
def server(production, worker_id):
    if production:
        # XXX Avoid the iframe
        yield 'https://lategenxer.streamlit.app/~/+'
        return

    host = '127.0.0.1'
    port = 8501 + (hash(worker_id) % 100)

    app = subprocess.Popen([
        'pipenv', 'run',
        'streamlit', 'run',
        '--server.address', host,
        '--server.port', str(port),
        '--server.headless', 'true',
        '--',
        'Home.py'
    ], stdout=subprocess.DEVNULL)

    # https://stackoverflow.com/a/19196218
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tries = 300
    result = sock.connect_ex((host, port))
    while result != 0 and tries > 0:
        tries -= 1
        time.sleep(0.010)
        result = sock.connect_ex((host, port))
    sock.close()
    print(tries)
    if result != 0:
        raise TimeoutError

    try:
        yield f'http://{host}:{port}'
    finally:
        app.terminate()
        app.wait()


@pytest.fixture(scope="session")
def driver(show_browser):
    options = Options()
    if not show_browser:
        options.add_argument('--headless=new')  #https://www.selenium.dev/blog/2023/headless-is-going-away/
        options.add_argument('--window-size=1080,1920')
        # https://stackoverflow.com/questions/45631715/downloading-with-chrome-headless-and-selenium/73840130#73840130
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

    try:
        # https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2204-Readme.md
        executable_dir = os.environ['CHROMEWEBDRIVER']
    except KeyError:
        from webdriver_manager.chrome import ChromeDriverManager
        executable_path = ChromeDriverManager().install()
    else:
        executable_path = os.path.join(executable_dir, "chromedriver")

    service = Service(executable_path=executable_path, log_output="chromedriver.log")

    driver = webdriver.Chrome(service=service, options=options)

    # https://statcounter.com/support/ignore-your-own-visits/
    # https://www.selenium.dev/documentation/webdriver/interactions/cookies/
    driver.get('https://www.statcounter.com/images/404.png')
    driver.add_cookie({
        'name': 'blocking',
        'value': '13036387'
    })

    try:
        yield driver
    finally:
        driver.quit()


# Use the same analytics anonymous ID.
analytics_cookie = {
    'name': 'ajs_anonymous_id',
    'value': 'ac78b155-525b-4578-97f6-58aa2f2bf366'
}


#
# Gilt Ladder Builder
#

@pytest.fixture(scope="function")
def gilt_ladder_page(server, driver):
    driver.get(server + '/Gilt_Ladder')

    driver.add_cookie(analytics_cookie)

    driver.implicitly_wait(15)
    driver.find_element(By.ID, 'test-marker')

    return driver


def test_gilt_ladder_default(gilt_ladder_page):
    driver = gilt_ladder_page

    driver.implicitly_wait(0)
    with pytest.raises(NoSuchElementException):
        driver.find_element(By.XPATH, "//div[@class='stException']")


def test_gilt_ladder_index_linked(gilt_ladder_page):
    driver = gilt_ladder_page

    index_linked = driver.find_element(By.XPATH, "//p[text()='Index-linked']")
    index_linked.click()

    time.sleep(3)

    driver.implicitly_wait(15)
    driver.find_element(By.ID, 'test-marker')

    driver.implicitly_wait(0)
    with pytest.raises(NoSuchElementException):
        driver.find_element(By.XPATH, "//div[@class='stException']")
        driver.save_screenshot('selenium.png')


def test_gilt_ladder_file_upload(gilt_ladder_page):
    driver = gilt_ladder_page

    advanced_tab = driver.find_element(By.XPATH, "//p[text()='Advanced']")
    advanced_tab.click()

    driver.implicitly_wait(15)

    # https://www.selenium.dev/documentation/webdriver/elements/file_upload/
    s = driver.find_element(By.XPATH, "//input[@type='file']")
    s.send_keys(os.path.join(data_dir, 'test_schedule.csv'))

    time.sleep(3)

    driver.find_element(By.ID, 'test-marker')
    driver.implicitly_wait(0)

    with pytest.raises(NoSuchElementException):
        driver.find_element(By.XPATH, "//div[@class='stException']")
        driver.save_screenshot('selenium.png')


#
# Capital Gains Calculator
#

@pytest.fixture(scope="function")
def cgtcalc_page(server, driver):
    driver.get(server + '/CGT_Calculator')

    driver.add_cookie(analytics_cookie)

    driver.implicitly_wait(15)
    driver.find_element(By.ID, 'test-marker')

    return driver


def test_cgtcalc_default(production, cgtcalc_page):
    driver = cgtcalc_page

    driver.implicitly_wait(0)
    with pytest.raises(NoSuchElementException):
        driver.find_element(By.XPATH, "//div[@class='stException']")

    driver.implicitly_wait(15)

    filename = os.path.join(data_dir, 'cgtcalc', 'jameshay-example.tsv')
    transactions = open(filename, 'rt').read()
    textarea = driver.find_element(By.XPATH, "//textarea")
    textarea.send_keys(transactions.replace('\t', ' '))

    actions = ActionChains(driver)
    actions.move_to_element(textarea)
    actions.key_down(Keys.CONTROL)
    actions.send_keys(Keys.ENTER)
    actions.key_up(Keys.CONTROL)
    actions.perform()

    time.sleep(3)

    iframe = driver.find_element(By.XPATH, "//iframe")
    srcdoc = iframe.get_attribute('srcdoc')

    if not production:
        from cgtcalc import calculate
        from report import HtmlReport

        result = calculate(open(filename, 'rt'))
        expected_html = io.StringIO()
        report = HtmlReport(expected_html)
        result.write(report)

        assert srcdoc == expected_html.getvalue()
