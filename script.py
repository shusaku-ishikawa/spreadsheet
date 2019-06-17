from __future__ import print_function
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import *
from selenium.webdriver.chrome.options import Options
from time import sleep 
import os, sys, datetime
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import gspread
from gspread.exceptions import *
from oauth2client.service_account import ServiceAccountCredentials
import shutil
import base64   
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

def get_today_and_month_ago():
    today = datetime.today()
    a_day_before = today - timedelta(days=1)
    a_month_ago = today - timedelta(days=30)
    return today, a_day_before, a_month_ago

def change_download_dir(driver, download_dir):
    driver.command_executor._commands["send_command"] = ("POST", '/session/$sessionId/chromium/send_command')
    driver.execute("send_command", {
        'cmd': 'Page.setDownloadBehavior',
        'params': {
            'behavior': 'allow',
            'downloadPath': download_dir # ダウンロード先
        }
    })
    return driver

def wait_csv_download(tempdir):
    downloaded_file = ""
    counter = 0
    max_loop_count = 10
    while True:
        counter += 1
        is_complete = False
        for filename in os.listdir(tempdir):
            if filename.endswith('.csv'):
                downloaded_file = os.path.join(tempdir, filename)
                is_complete = True
        else:
            sleep(1)
        if is_complete:
            return downloaded_file
        if counter > max_loop_count:
            print('CSVダウンロードに失敗しました')
            return False

''' Chromeドライバの初期設定 '''
def init_selenium():
    ###Chromeへオプションを設定
    chop = webdriver.ChromeOptions() #
    chop.add_argument('--ignore-certificate-errors') #SSLエラー対策
    chop.add_argument('--disable-dev-shm-usage')
    chop.add_argument('--headless')
    chop.add_argument('--no-sandbox')
    chop.add_argument('--disable-gpu')
    chop.add_argument("user-data-dir=selenium") 
    chop.add_argument('--window-size=1280,1024')
    chop.add_argument('log-level=3')
    driver = webdriver.Chrome(options = chop)
    driver.implicitly_wait(5) # seconds
    driver.delete_all_cookies()
    return driver

''' A8 ダウンロード '''
def download_from_a8(driver, book, tempdir):
    print('***** A8の処理を開始します ******')
    url = "https://www.a8.net/"
    id = "tomokifor"
    password = "forcompany0131"


    print('////// A8の処理を開始します ///////')
    while True:
        driver.get(url)
        ''' ログイン ''' 
        driver.execute_script("document.getElementById('asLoginId').setAttribute('value','" + id + "');")
        driver.execute_script("document.getElementsByName('passwd')[0].setAttribute('value','" + password + "');")
        driver.find_elements_by_xpath('//*[@id="headerLeft"]/form/ul/li[3]/input')[0].click()
        
        ''' 日付計算 '''
        today, _, a_month_ago = get_today_and_month_ago()
        today_str = today.strftime('%Y/%m/%d')
        a_month_ago_str = a_month_ago.strftime('%Y/%m/%d')

        ''' コンバージョンレファラ '''
        ''' マルスオーバしてクリック '''
        actions = ActionChains(driver)
        actions.move_to_element(driver.find_element_by_xpath('//*[@id="globalMenu"]/li[1]/div')).perform()
        
        try:
            driver.find_element_by_link_text('新レポートβ版').click()
            break
        except NoSuchElementException:
            driver.save_screenshot('before_beta_repot.png')
            pass

    driver.find_elements_by_xpath('//*[@id="reportList"]/li[3]/a')[0].click()
    
    ''' 過去１ヶ月の期間入力 '''
    driver.execute_script("document.getElementById('jquery-ui-datepicker-from').setAttribute('value','" + a_month_ago_str + "');")
    driver.execute_script("document.getElementById('jquery-ui-datepicker-to').setAttribute('value','" + today_str + "');")
    driver.find_elements_by_xpath('//*[@id="sitereport"]/form/ul/li[2]/input')[0].click()

    csv_export = driver.find_element_by_xpath('//*[@id="sitereport"]/span/a[1]/span')
    driver.execute_script("arguments[0].click();", csv_export)
    
    ''' ダウンロードを待ってシートに転記 '''
    

    paste_csv_to_gspread(book, 'A8', downloaded_file, 'A1')
    os.remove(downloaded_file)
    print('////// A8の処理が完了しました ///////')

    print('////// ポイントレポートの処理を開始します ///////')
    ''' ポイントレポート '''
    ''' マウスオーバでリンクをクリック '''
    actions = ActionChains(driver)
    actions.move_to_element(driver.find_element_by_xpath('//*[@id="globalMenu"]/li[1]/div')).perform()
    driver.find_element_by_link_text('ポイントレポート').click()
    
    ''' 開始年月日を１ヶ月前にセット '''
    driver.execute_script("document.getElementsByName('startYear')[0].setAttribute('value','" + str(a_month_ago.year) + "');")
    driver.execute_script("document.getElementsByName('startMonth')[0].setAttribute('value','" + str(a_month_ago.month) + "');")
    driver.execute_script("document.getElementsByName('startDay')[0].setAttribute('value','" + str(a_month_ago.day) + "');")
    

    ''' 発生ベースとする '''
    base_select = Select(driver.find_element_by_xpath('//*[@id="report"]/table/tbody/tr[3]/td/select'))
    base_select.select_by_value('0')

    ''' 検索し、csvエクスポート ''' 
    driver.find_element_by_xpath('//*[@id="reportList"]/ul/li[1]/input').click()
    csv_export = driver.find_element_by_xpath('//*[@id="mainAreaReport"]/span/a[1]/span')
    driver.execute_script('arguments[0].click();', csv_export)

    ''' ダウンロードを待ってシートに転記 '''
    downloaded_file = wait_csv_download(tempdir)
    paste_csv_to_gspread(book, 'A8_ポイントレポート', downloaded_file, 'A1')
    
    os.remove(downloaded_file)
    print('////// ポイントレポートの処理が完了しました ///////')
    print('***** A8の処理が完了しました ******')
    shutil.rmtree(tempdir)

''' AFB ダウンロード '''
def download_from_afb(driver, book, tempdir):
    print('***** AFBの処理を開始します ******')
    url = "https://www.afi-b.com/"
    id = "tomokifor"
    password = "forcompany1128"

    
    ''' 成果状況確認 '''
    while True:
        try:
            driver.get(url)
            ''' ログイン '''
            driver.execute_script("document.getElementsByName('login_name')[0].setAttribute('value','" + id + "');")
            driver.execute_script("document.getElementsByName('password')[0].setAttribute('value','" + password + "');")
            driver.find_element_by_xpath('//*[@id="pageTitle"]/aside[1]/g-header-loginform/div[1]/form/div/div[3]/m-btn/div/input').click()
            driver.find_element_by_xpath('//*[@id="GlobalMenu"]/li[3]/a').click()
            driver.save_screenshot('before_30d.png')
            driver.find_element_by_xpath('//*[@id="form_span" and @value="30d"]').click()
            break
        except ElementClickInterceptedException:
            pass
    driver.find_element_by_xpath('//*[@id="Contents"]/form/div/div/div/div/div/div[1]/table[2]/tbody/tr/td[3]/p/input').click()
    
    ''' ダウンロードを待ってシートに転記 '''
    downloaded_file = wait_csv_download(tempdir)
    paste_csv_to_gspread(book, 'AFB', downloaded_file, 'A1')
    os.remove(downloaded_file)

    print('***** AFBの処理が完了しました ******')
    shutil.rmtree(tempdir)

def download_from_actr(driver, book, tempdir):
    print('***** アクトレの処理を開始します ******')
    url = "https://www.accesstrade.ne.jp/"
    id = "tomoki_for"
    password = "forcompany901"

    driver.get(url)
    ''' ログイン '''
    driver.execute_script("document.getElementsByName('userId')[0].setAttribute('value', '" + id + "');")
    driver.execute_script("document.getElementsByName('userPass')[0].setAttribute('value', '" + password + "');")
    driver.find_element_by_xpath('//*[@id="login_p"]/form/input').click()

    ''' レポート '''
    driver.find_element_by_xpath('//*[@id="gloval_nav"]/ul/li[3]/a').click()
    driver.find_element_by_xpath('//*[@id="aside_nav"]/ul/li[12]/a').click()

    ''' 日付取得, セット '''
    today, _, a_month_ago = get_today_and_month_ago()
    to_year = Select(driver.find_element_by_id('targetYearTo'))
    to_month = Select(driver.find_element_by_id('targetMonthTo'))
    to_day = Select(driver.find_element_by_id('targetDayTo'))
    to_year.select_by_value(str(today.year))
    to_month.select_by_value(str(today.month))
    to_day.select_by_value(str(today.day))

    from_year = Select(driver.find_element_by_id('targetYearFrom'))
    from_month = Select(driver.find_element_by_id('targetMonthFrom'))
    from_day = Select(driver.find_element_by_id('targetDayFrom'))
    from_year.select_by_value(str(a_month_ago.year))
    from_month.select_by_value(str(a_month_ago.month))
    from_day.select_by_value(str(a_month_ago.day))

    ''' 検索、ダウンロード '''
    driver.find_element_by_id('search_btn').click()
    driver.find_element_by_id('download_btn').click()

    ''' ダウンロード待って転記 '''
    downloaded_file = wait_csv_download(tempdir)
    paste_csv_to_gspread(book, 'アクトレ_ポイントレポート', downloaded_file, 'A1')
    os.remove(downloaded_file)
    print('***** アクトレの処理が完了しました ******')
    shutil.rmtree(tempdir)

def download_from_alladmin(driver, book, tempdir):
    print('***** NMの処理を開始します ******')
    
    url = "https://www.all-adin.jp/login.php"
    id = "owkbzfcm"
    password = "Forcompany515"
    anken_no = "1303"

    today, _, a_month_ago = get_today_and_month_ago()

    driver.get(url)

    ''' ログイン '''
    driver.execute_script('document.getElementById("id").setAttribute("value", "' + id + '");')
    driver.execute_script('document.getElementById("password").setAttribute("value", "' + password + '");')
    driver.find_element_by_xpath('/html/body/div[2]/form/table/tbody/tr[4]/td/input[1]').click()
    driver.find_element_by_xpath('//*[@id="wrapper"]/table[2]/tbody/tr/td[6]/a/img').click()
    driver.execute_script('document.getElementById("anken_id").setAttribute("value", "' + anken_no + '");')

    ''' 期間入力 ''' 
    todaystr = today.strftime('%Y-%m-%d')
    monthagostr = a_month_ago.strftime('%Y-%m-%d')
    driver.find_element_by_id('date_type2').click()
    driver.execute_script('document.getElementById("from").setAttribute("value", "' + monthagostr + '");')
    driver.execute_script('document.getElementById("to").setAttribute("value", "' + todaystr + '");')
    
    ''' 検索 ''' 
    driver.find_element_by_id('search').click()

    ''' DL '''
    driver.find_element_by_xpath('//*[@id="tbl-result-media"]/tbody/tr[1]/td[9]/a').click()
    
    ''' ダウンロードを待って転記 '''
    downloaded_file = wait_csv_download(tempdir)
    paste_csv_to_gspread(book, 'NM', downloaded_file, 'A1')
    os.remove(downloaded_file)
    print('***** NMの処理が完了しました ******')
    shutil.rmtree(tempdir)
def next_available_row(worksheet):
    str_list = list(filter(None, worksheet.col_values(1)))  # fastest
    return str(len(str_list)+1)

def kosuiso(driver, book):
    print('***** kosuisoの処理を開始します ******')
    target_sheet_name = '酵水素'
    url_with_id_pass = "https://for0501:20180501@kosuiso.jp/media_adv/"
    
    code_list = [
        'JAM1hvbhwpo', # 定期初回1袋半額_定期縛り無し(383_d_tan_ad_tsn)3
        'JAM18donppo', # 定期初回1袋半額_定期縛り無し(383_d_tan_ad_tsn)
        'JAM18deynpo', # 定期初回1袋半額_定期縛り無し(383_p_tsn)
        'JAM18do3opo', # 定期初回1袋半額_定期縛り無し(383_d_tan_ad_tsn)
        'JAM14y8rkp22221111o', # ③スムージー_橋本マナミ1980円
        'JAM1xadurp22221111o', # ②スムージー_橋本マナミ1980円
        'JAM1462oup11111111o', # スムージー_初回特別1980円(462)
        'JAM1ManHMp22221111o' # スムージー_橋本マナミ1980円
    ]

    driver.get(url_with_id_pass)
    
    ''' 期間を前日にセット '''
    _, a_day_before , _ = get_today_and_month_ago()
    search_startyear = Select(driver.find_element_by_xpath('//*[@id="search_form1"]/div[1]/table/tbody/tr[3]/td[2]/select[1]'))
    search_startmonth = Select(driver.find_element_by_xpath('//*[@id="search_form1"]/div[1]/table/tbody/tr[3]/td[2]/select[2]'))
    search_startday = Select(driver.find_element_by_xpath('//*[@id="search_form1"]/div[1]/table/tbody/tr[3]/td[2]/select[3]'))

    search_endyear = Select(driver.find_element_by_xpath('//*[@id="search_form1"]/div[1]/table/tbody/tr[3]/td[2]/select[4]'))
    search_endmonth = Select(driver.find_element_by_xpath('//*[@id="search_form1"]/div[1]/table/tbody/tr[3]/td[2]/select[5]'))
    search_endday = Select(driver.find_element_by_xpath('//*[@id="search_form1"]/div[1]/table/tbody/tr[3]/td[2]/select[6]'))
    
    search_startyear.select_by_value(str(a_day_before.year))
    search_startmonth.select_by_value(str(a_day_before.month))
    search_startday.select_by_value(str(a_day_before.day))
    
    search_endyear.select_by_value(str(a_day_before.year))
    search_endmonth.select_by_value(str(a_day_before.month))
    search_endday.select_by_value(str(a_day_before.day))

    driver.find_element_by_xpath('//*[@id="search_form1"]/div[1]/table/tbody/tr[3]/td[2]/input').click()

    try:
        sheet = book.worksheet(target_sheet_name)
    except WorksheetNotFound:
        print('タブ: ' + target_sheet_name + ' が見つかりませんでした。新規作成します。')
        sheet = book.add_worksheet(title=target_sheet_name, rows=1000, cols=30)
    
    monthday = str(a_day_before.month) + '/' + str(a_day_before.day)
    try:
        target = sheet.find(monthday)
        r = target.row
    except CellNotFound:
        r = next_available_row(sheet)
        sheet.update_acell('A' + str(r), monthday)
    
    ascii_code = 66 # B
    for code in code_list:
        print('code: ' + code + ' の処理を開始します。')
        
        try:
            link = driver.find_element_by_link_text(code)
            count = int(link.find_element_by_xpath('../../td[14]').text.replace('件', ''))
        except:
            print('code: ' + code + ' が見つかりませんでした')
            count = 0        
        
        sheet.update_acell(chr(ascii_code) + str(r), count)
        ascii_code += 1
        print('code: ' + code + ' の処理が完了しました。')
        
    print('***** kosuisoの処理が完了しました ******')
    
def ebis_net(driver, book):
    print('***** ebis netの処理を開始します ******')
    
    target_sheet_name = 'EBiS'
    url = "https://id.ebis.ne.jp/"
    account_key = 'bglen'
    username = 'bg_01'
    password = 'ladvbglen1'

    code_list = [
        'bglenwhitefor001', # コンテンツ_ホワイト_アドバリュー2_FOR1_SEM
        'bglenwhitefor002', # コンテンツ_ホワイト_アドバリュー2_FOR2_SEM
        'bglenwhitefor003' # コンテンツ_ホワイト_アドバリュー2_FOR3_SEM
    ]

    _, a_day_before, _ = get_today_and_month_ago()
    
    driver.get(url)
    driver.execute_script('document.getElementById("account_key").setAttribute("value", "' +  account_key + '");')
    driver.execute_script('document.getElementById("username").setAttribute("value", "' +  username + '");')
    driver.execute_script('document.getElementById("password").setAttribute("value", "' +  password + '");')
    driver.find_element_by_xpath('/html/body/div[1]/div/div/div[1]/div/form/div/div[4]/div/button').click()

    monthday = str(a_day_before.month) + '/' + str(a_day_before.day)
    try:
        sheet = book.worksheet(target_sheet_name)
    except WorksheetNotFound:
        print('タブ: ' + target_sheet_name + ' が見つかりませんでした。新規作成します。')
        sheet = book.add_worksheet(title=target_sheet_name, rows=1000, cols=30)
    
    
    try:
        target = sheet.find(monthday)
        r = target.row
    except CellNotFound:
        r = next_available_row(sheet)
        sheet.update_acell('A' + str(r), monthday)

    ascii_code = 66 # B
    for code in code_list:
        print('code: ' + code + ' の処理を開始します。')
        try: 
            link = driver.find_element_by_link_text(code)
            count = int(link.find_element_by_xpath('../../td[6]').text)
        except:
            count = 0  

        sheet.update_acell(chr(ascii_code) + str(r), count)
        ascii_code += 1
        print('code: ' + code + ' の処理が完了しました。')
        
    print('***** belta shopの処理が完了しました ******')
    
def belta_shop(driver, book):
    print('***** belta shopの処理を開始します ******')
    target_sheet_name = 'belta'
    url_with_id_pass = 'https://dkdk:admin123@belta-shop.jp/media_adv/'
    code_list = [
        'fmj7gjj81st', # こうじ_アフィリエイト_DK
        'fmj7fzuusst', # こうじ_アフィリエイト_DK
        'fmj78dhcxst' # こうじ_アフィリエイト_DK
    ]
    
    _, a_day_before, _ = get_today_and_month_ago()

    driver.get(url_with_id_pass)

    search_startyear = Select(driver.find_element_by_xpath('//*[@id="search_form1"]/div[1]/table/tbody/tr[3]/td[2]/select[1]'))
    search_startmonth = Select(driver.find_element_by_xpath('//*[@id="search_form1"]/div[1]/table/tbody/tr[3]/td[2]/select[2]'))
    search_startday = Select(driver.find_element_by_xpath('//*[@id="search_form1"]/div[1]/table/tbody/tr[3]/td[2]/select[3]'))

    search_endyear = Select(driver.find_element_by_xpath('//*[@id="search_form1"]/div[1]/table/tbody/tr[3]/td[2]/select[4]'))
    search_endmonth = Select(driver.find_element_by_xpath('//*[@id="search_form1"]/div[1]/table/tbody/tr[3]/td[2]/select[5]'))
    search_endday = Select(driver.find_element_by_xpath('//*[@id="search_form1"]/div[1]/table/tbody/tr[3]/td[2]/select[6]'))
    
    search_startyear.select_by_value(str(a_day_before.year))
    search_startmonth.select_by_value(str(a_day_before.month))
    search_startday.select_by_value(str(a_day_before.day))

    search_endyear.select_by_value(str(a_day_before.year))
    search_endmonth.select_by_value(str(a_day_before.month))
    search_endday.select_by_value(str(a_day_before.day))
    
    driver.find_element_by_xpath('//*[@id="search_form1"]/div[1]/table/tbody/tr[3]/td[2]/input').click()
    
    monthday = str(a_day_before.month) + '/' + str(a_day_before.day)
    try:
        sheet = book.worksheet(target_sheet_name)
    except WorksheetNotFound:
        print('タブ: ' + target_sheet_name + ' が見つかりませんでした。新規作成します。')
        sheet = book.add_worksheet(title=target_sheet_name, rows=1000, cols=30)
    
    
    try:
        target = sheet.find(monthday)
        r = target.row
    except CellNotFound:
        r = next_available_row(sheet)
        sheet.update_acell('A' + str(r), monthday)
    
    ascii_code = 66 #B
    for code in code_list:
        print('code: ' + code + ' の処理を開始します。')
        try:
            link = driver.find_element_by_link_text(code)
            count = int(link.find_element_by_xpath('../../td[14]').replace('件', ''))
        except:
            count = 0
        sheet.update_acell(chr(ascii_code) + str(r), count)
        ascii_code += 1
        print('code: ' + code + ' の処理が完了しました。')
    print('***** belta shopの処理が完了しました ******')
    
def yahoo(driver, book, tempdir):
    print('***** Yahooの処理を開始します ******')
    print('///// レポートダウンロードを開始します /////')
    url = 'https://promotionalads.business.yahoo.co.jp/Advertiser/Dashboard'
    business_id = 'dhai7155sifted'
    password = '332191-Aa'

    driver.get(url)

    driver.execute_script('document.getElementById("user_name").setAttribute("value", "' + business_id + '");')
    driver.execute_script('document.getElementById("password").setAttribute("value", "' + password + '");')
    driver.save_screenshot('before_filling.png')
    driver.find_element_by_xpath('//*[@id="bidlogin"]/div/div/form/fieldset/div[3]/input').click()

    driver.save_screenshot('before_link_click.png')
    driver.find_element_by_xpath('//*[@id="app"]/div/div/div/div[3]/ul/li[2]/a').click()
    driver.find_element_by_link_text('レポート').click()
    driver.save_screenshot('after_report_click.png')

    driver.find_element_by_xpath('//*[@id="contents"]/div/div/div[1]/div/div/div[2]/div[1]/div/div[1]').click()
    driver.save_screenshot('before_account_select.png')
    
    account_count = len(driver.find_elements_by_xpath('//*[@id="contents"]/div/div/div[1]/div/div/div[2]/div[1]/div/div[2]/div/div/div/ul/li'))
    driver.find_element_by_xpath('//*[@id="contents"]/div/div/div[1]/div/div/div[2]/div[1]/div/div[1]').click()
    
    for i in range(account_count):
        driver.find_element_by_xpath('//*[@id="contents"]/div/div/div[1]/div/div/div[2]/div[1]/div/div[1]').click()
        driver.save_screenshot('before_li_click.png')
        account_li = driver.find_element_by_xpath('//*[@id="contents"]/div/div/div[1]/div/div/div[2]/div[1]/div/div[2]/div/div/div/ul/li[' + str(i + 1) + ']' )
        account_name = account_li.text
        print(account_name + 'のレポートを開始します。')
        account_li.click()
        download_link = driver.find_element_by_xpath('//*[@id="listTable"]/tbody/tr[1]/td[2]/a')
        driver.execute_script("arguments[0].click();", download_link)

        downloaded_file = wait_csv_download(tempdir)
        paste_csv_to_gspread(book, 'YSS_' + account_name, downloaded_file, 'A1')
        os.remove(downloaded_file)
        print(account_name + 'のレポートの貼り付けが完了しました。')
    print('///// レポートダウンロードが完了しました /////')

    ''' YDN start '''
    print('///// YDNの処理を開始します /////')
    driver.find_element_by_xpath('/html/body/div[1]/div[1]/div[3]/ul/li[3]/a').click()
    driver.find_element_by_link_text('レポート').click()
    driver.find_element_by_xpath('//*[@id="contentsRoot"]/div/div/span/div[2]/div[2]/div[2]/div[2]/div[3]/div/div[1]/table/tbody/tr[1]/td[3]/a').click()
    
    downloaded_file = wait_csv_download(tempdir)
    paste_csv_to_gspread(book, 'YDN_SlimMagazine', downloaded_file, 'A1' )
    print('SlimMagazineのレポートの貼り付けが完了しました。')

    print('///// YDNの処理が完了しました /////')
    print('***** Yahooの処理が完了しました ******')
    shutil.rmtree(tempdir)   

def get_gspread_book(secret_key, book_name):
    scope = ['https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive']

    credentials = ServiceAccountCredentials.from_json_keyfile_name(secret_key, scope)
    gc = gspread.authorize(credentials)
    book = gc.open(book_name)
    return book

def paste_csv_to_gspread(book, sheet_name, csv_file, cell):
    try:
        sheet = book.worksheet(sheet_name)
    except WorksheetNotFound:
        print('タブ: ' + sheet_name + ' が見つかりませんでした。新規作成します。')
        sheet = book.add_worksheet(title=sheet_name, rows=1000, cols=30)

    (firstRow, firstColumn) = gspread.utils.a1_to_rowcol(cell)

    with open(csv_file, 'r', encoding='shift_jis') as f:
        content = f.read()
    body = {
        'requests': [{
            'pasteData': {
                "coordinate": {
                    "sheetId": sheet.id,
                    "rowIndex": firstRow-1,
                    "columnIndex": firstColumn-1,
                },
                "data": content,
                "type": 'PASTE_NORMAL',
                "delimiter": ',',
            }
        }]
    }
    return book.batch_update(body)


def connect_gmailapi(picklefile, client_id_json):
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    # If modifying these scopes, delete the file token.pickle.
    scope = ['https://www.googleapis.com/auth/gmail.readonly']

    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(picklefile):
        with open(picklefile, 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                client_id_json, scope)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open(picklefile, 'wb') as token:
            pickle.dump(creds, token)

    return build('gmail', 'v1', credentials=creds)

def get_shizen_message_id(service, subject_keyword):

    msgidlist = []

    query = 'Subject:' + subject_keyword

    # メールIDの一覧を取得する(最大1件)
    msgidlist = service.users().messages().list(userId='me',maxResults=1,q=query).execute()['messages']
    if len(msgidlist) == 0:
        print('メールが取得できませんでした')
        return None
    
    return msgidlist[0]['id']

def download_attachment(service, user_id, msg_id, store_dir):

    """Get and store attachment from Message with given id.

    Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    msg_id: ID of Message containing attachment.
    prefix: prefix which is added to the attachment filename on saving
    """
    try:
        message = service.users().messages().get(userId=user_id, id=msg_id).execute()
        for part in message['payload']['parts']:
            newvar = part['body']
            if 'attachmentId' in newvar:
                att_id = newvar['attachmentId']
                att = service.users().messages().attachments().get(userId=user_id, messageId=msg_id, id=att_id).execute()
                data = att['data']
                file_data = base64.urlsafe_b64decode(data.encode('UTF-8'))
                
                path = os.path.join(store_dir, part['filename'])
                f = open(path, 'wb')
                f.write(file_data)
                f.close()
                return path
    except Exception as e:
        print('An error occurred: %s' % e)  

def from_gmail(book, tempdir):
    print('***** Gmailの処理を開始します ******')

    picklefile = 'secret_key/token.pickle'
    clientidjson = 'secret_key/client_id.json'
    
    service = connect_gmailapi(picklefile, clientidjson)
    today, _, _ = get_today_and_month_ago()

    ''' Shizen '''
    print('////// Shizen CSVの処理を開始します ////////')
    subject_keyword = 'FoR様' + today.strftime('%Y-%m-%d')
    msg_id = get_shizen_message_id(service, subject_keyword)
    downloaded_file = download_attachment(service, 'me', msg_id, download_base_mail_dir)
    paste_csv_to_gspread(book, 'shizen', downloaded_file, 'A1')
    print('////// Shizen CSVの処理が完了しました ////////')

    print('***** Gmailの処理が完了しました ******')

''' 以下メイン処理 '''
if __name__ == '__main__':
    
    argvs = sys.argv
    
    secret_key = 'secret_key/lancers01-e93298c251a1.json'
    book_name = '成果管理シート'

    try:
        book = get_gspread_book(secret_key, book_name)
    except SpreadsheetNotFound:
        print('スプレットシート: ' + book_name + ' が見つかりませんでした')
        sys.exit()

    #driver = init_selenium()
    
    download_base_dir = os.path.join(os.getcwd(), 'temp')
    ''' ダウンロードの基本フォルダがなければ作成 '''
    if not os.path.exists(download_base_dir):
        os.mkdir(download_base_dir)
    
    # ''' a8 '''
    # download_base_a8_dir = os.path.join(download_base_dir, 'a8')
    # if not os.path.exists(download_base_a8_dir):
    #     os.mkdir(download_base_a8_dir)
    # change_download_dir(driver, download_base_a8_dir)
    # download_from_a8(driver, book, download_base_a8_dir)
    # ''''''
    
    # ''' AFB '''
    # download_base_afb_dir = os.path.join(download_base_dir, 'afb')
    # if not os.path.exists(download_base_afb_dir):
    #     os.mkdir(download_base_afb_dir)
    # change_download_dir(driver, download_base_afb_dir)
    # download_from_afb(driver, book, download_base_afb_dir)
    # ''''''

    # ''' アクトレ '''
    # download_base_actr_dir = os.path.join(download_base_dir, 'actr')
    # if not os.path.exists(download_base_actr_dir):
    #     os.mkdir(download_base_actr_dir)
    # change_download_dir(driver, download_base_actr_dir)
    # download_from_actr(driver, book, download_base_actr_dir)
    # ''''''

    # ''' NM '''
    # download_base_nm_dir = os.path.join(download_base_dir, 'nm')
    # if not os.path.exists(download_base_nm_dir):
    #     os.mkdir(download_base_nm_dir)
    # change_download_dir(driver, download_base_nm_dir)
    # download_from_alladmin(driver, book, download_base_nm_dir)
    # ''''''


    # ''' 酵水素 '''
    # kosuiso(driver, book)
    # ''''''
    # ''' ebis net '''
    # ebis_net(driver, book)
    # ''''''

    # ''' belta  '''
    # belta_shop(driver, book)
    # ''''''

    ''' Yahoo '''
    # download_base_yahoo_dir = os.path.join(download_base_dir, 'yahoo')
    # if not os.path.exists(download_base_yahoo_dir):
    #     os.mkdir(download_base_yahoo_dir)
    # change_download_dir(driver, download_base_yahoo_dir)
    # yahoo(driver, book, download_base_yahoo_dir)
    ''''''

    ''' メールから '''
    download_base_mail_dir = os.path.join(download_base_dir, 'mail')
    if not os.path.exists(download_base_mail_dir):
        os.mkdir(download_base_mail_dir)
    from_gmail(book, download_base_mail_dir)

    ''' ドライバを閉じる '''
    #driver.close()

