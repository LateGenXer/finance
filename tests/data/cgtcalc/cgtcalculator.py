#!/usr/bin/env python3
#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


#
# Script that uses Selenium to automate obtaining reference results from CGTCalculator.
#


import os.path
import time
import sys

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


headless = not sys.stdin.isatty()


def main():
    options = Options()
    if headless:
        options.add_argument('--headless=new')  #https://www.selenium.dev/blog/2023/headless-is-going-away/
        options.add_argument('--window-size=1080,1920')
        # https://stackoverflow.com/questions/45631715/downloading-with-chrome-headless-and-selenium/73840130#73840130
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

    prefs = {"download.default_directory" : os.getcwd()}
    options.add_experimental_option('prefs', prefs)

    executable_path = ChromeDriverManager().install()

    service = Service(executable_path=executable_path, log_output="chromedriver.log")

    driver = webdriver.Chrome(service=service, options=options)

    driver.get('http://www.cgtcalculator.com/calculator.aspx')

    driver.implicitly_wait(20)

    if False:
        rounding = driver.find_element(By.ID, 'Rounding')
        rounding.click()

    for arg in sys.argv[1:]:
        rows = []
        for line in open(arg, 'rt'):
            line = line.rstrip('\n')
            if line.startswith('#'):
                continue
            fields = line.split()
            if not fields:
                continue
            if fields[0] in ('B', 'BUY', 'S', 'SELL'):
                fields.append('0')
            rows.append(' '.join(fields) + '\n')

        # Avoid Tabs as they change focus
        trades_input = ''.join(rows)

        trades = driver.find_element(By.ID, 'TEXTAREA1')
        trades.send_keys(trades_input)

        calculate = driver.find_element(By.ID, 'Button1')
        calculate.click()

        time.sleep(5)

        results = driver.find_element(By.ID, 'Textarea2')

        # https://stackoverflow.com/a/72787948
        output = results.get_property('textContent')
        assert isinstance(output, str)

        sys.stdout.write(output)

        name, _ = os.path.splitext(arg)
        open(name + '.txt', 'wt').write(output)

        if False:
            input()

    driver.quit()


main()
