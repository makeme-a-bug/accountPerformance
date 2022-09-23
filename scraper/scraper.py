import random
import time
from typing import Dict,List,Any,Union
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from .utils import solve_captch
from rich.console import Console
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException , NoSuchElementException
from selenium.webdriver.support.wait import WebDriverWait
from dateutil.parser import parse
import pandas as pd
import re
class Scraper(webdriver.Remote):

    def __init__(self,profile_name:str,profile_uuid:str, url:List[str], command_executor:str, destroy_browser:bool = False , tracker:List = [] ) -> None:
        self.command_executor = command_executor
        # self.capabilities = desired_capabilities
        self.profile_name = profile_name
        self.profile_uuid = profile_uuid
        self.url = url
        self.destroy_browser = destroy_browser
        self.console = Console()
        self.tracker = tracker
        self.current_page = 1
        self.max_page = 4

        super(Scraper,self).__init__(self.command_executor,desired_capabilities={})
        self.set_page_load_timeout(120)
        self.implicitly_wait(120)
        try:
            self.maximize_window()
        except:
            pass


    def get_data(self):
        """
        Starts reporting for the urls and profile given in the initial
        """
        links = []
        if self.get_page(self.url):
            # self.increase_table_size()
            # time.sleep(10)
            if self.wait_for_table():
                while True:
                    temp_links = self.get_links()
                    links.extend(temp_links)
                    if not self.get_next_page():
                        break
        self.console.log(f"Got {len(links)} rows")
        self.console.log(f"getting data")
        results = [ self.get_texts(l) for l in links]
        return results
        # self.quit()

    def increase_table_size(self):
        self.bring_to_front()
        select = self.find_elements(By.CLASS_NAME,"kat-select-container")[0]
        select.click()
        option = select.find_element(By.CLASS_NAME,"option-inner-container")
        element = option.find_element(By.CSS_SELECTOR,"div[data-value='100']")
        element.click()


    def bring_to_front(self):
        try:
            self.minimize_window()
        except:
            pass
        try:
            self.maximize_window()
        except:
            pass

    def get_texts(self,link):
        
        result = {
            'Subject':"",
            'Date':"",
            "Performance Notification":"",
            "ASIN(s)":"",
        }
        if self.get_notification_page(link):
            current_window = self.current_window_handle
            media_body = self.find_element(By.CLASS_NAME,"media-body")
            result["Date"] = media_body.find_element(By.TAG_NAME,"div").text
            result["Subject"] = media_body.find_element(By.TAG_NAME,"h3").text
            iframe = self.find_element(By.CLASS_NAME,"starfleet-sanitized-iframe")
            iframe = self.switch_to.frame(iframe) 
            body = self.find_element(By.TAG_NAME, "body")
            result["Performance Notification"] = body.text
            asin = re.findall(r'ASIN: (\w+)',result["Performance Notification"])
            if len(asin) > 0:
                result["ASIN(s)"] = asin[0][:10]
            
            self.switch_to.window(current_window)
            
        return result

    def get_notification_page(self,url):
        url_open = False
        self.get(url)
        time.sleep(3)
        self.implicitly_wait(20)        

        for i in range(3):
            try:
                captcha = self.solve_captcha()
                logged_in = self.is_profile_logged_in()
                if captcha and logged_in:
                    WebDriverWait(self, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR,"a[href*='/performance/notifications']")))
                    url_open = True
                else:
                    pass
                break
            except TimeoutException:
                self.bring_to_front()
                self.get(url)
        self.implicitly_wait(120)
        return url_open


    def get_links(self):
        self.console.log(f"getting rows")
        rows = self.find_elements(By.CSS_SELECTOR,"kat-table-row[class*='d-sm-table-row']")
        links = []
        if rows:
            for row in rows[1:]:
                cols = row.find_elements(By.TAG_NAME,"kat-table-cell")
                link = None
                if cols:
                    link_col = cols[0].find_element(By.TAG_NAME,"a")
                    link = link_col.get_attribute("href")
                if link:
                    links.append(link)

        self.implicitly_wait(120)
        return links
    
    def wait_for_table(self):
        table_loaded = False
        for i in range(2):
            try:
                self.implicitly_wait(20)
                WebDriverWait(self, 20).until(EC.presence_of_element_located((By.CLASS_NAME,"starfleet-notification-row")))
                self.console.log(f"table for page:{self.current_page}",style="blue")
                table_loaded = True
                break
            except TimeoutException:
                continue
        self.implicitly_wait(120)
        return table_loaded

    def get_page(self,url:str) -> None:
        """
        gets the url in the browser.\n
        parameters:\n
        url:<str>
        returns:\n
        None
        """
        url_open = False
        self.get(url)
        time.sleep(3)
        for i in range(3):
            try:
                captcha = self.solve_captcha()
                logged_in = self.is_profile_logged_in()
                if captcha and logged_in:
                    self.bring_to_front()
                    WebDriverWait(self, 60).until(EC.presence_of_element_located((By.CLASS_NAME,"kat-select-container")))
                    url_open = True
                    self.console.log(f"page loaded")
                else:
                    pass
                break
            except TimeoutException:
                self.get(url)
        return url_open

    def solve_captcha(self) -> bool:
        """
        Checks if captcha appreared on the page.if appeared will try to solve it.
        return:
        True  : if captcha was solved
        False : if captcha was not solved
        """

        if "Try different image" in self.page_source:
            self.console.log(f"Captcha appear for profile [{self.profile_uuid}]")
            if not solve_captch(self):
                self.console.log(f"CAPTCHA not solved")
                return False
        return True
    
    def is_profile_logged_in(self) -> bool:
        """
        Checks if the multilogin is logged into amazon \n
        returns:\n
        True  : if the profile is logged in
        False : if the profile is not logged in
        """
        time.sleep(10)
        if "By continuing, you agree to Amazon's" not in self.page_source:
            return True
        self.console.log(f"{self.profile_name}:Profile not logged in into Amazon account",style='red')
        return False

    
    def get_next_page(self):
        if self.current_page >= self.max_page:
            return False
        self.implicitly_wait(20)
        while True:
            elements = self.find_elements(By.CLASS_NAME,f"page-{self.current_page+1}")
            time.sleep(2)
            if len(elements)>0:
                elements[0].click()
                time.sleep(5)
                clicked = self.find_elements(By.CLASS_NAME,f"page-{self.current_page+1}")
                clicked = clicked[0].get_attribute("class")
                if "selected" in clicked:
                    self.current_page += 1
                    self.wait_for_table() 
                    self.implicitly_wait(120)
                    return True
                else:
                    self.console.log("next page button clicked but table was not updated. if you see this message multiple times. bring the browser to the front so it is loaded correctly",style="yellow")
                    self.bring_to_front()
                    time.sleep(10)
                    continue
            else:
                self.console.log("end of table",style="blue")
                self.implicitly_wait(120)
                return False



    def __exit__(self, *args) -> None:
        if self.destroy_browser:
            self.quit()
            time.sleep(5)
