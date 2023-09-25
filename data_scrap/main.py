import time
from typing import List

from selenium import webdriver
from bs4 import BeautifulSoup
import pandas as pd
from selenium.common import ElementClickInterceptedException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait



class EkstraklasaScrapper:
    def __init__(self, season_number):
        # https://www.ekstraklasa.org/terminarz only display 3 last seasons
        self.season_number = season_number
        self.driver = webdriver.Chrome()
        self.round = ''
        self.seasons = [
             '2021_2022',
             '2022_2023',
             '2023_2024'
        ]

    def get_column_names(self) -> List[str]:
        col_names = ['possession', 'shots', 'shots_on_target', 'corners', 'passes', 'accurate_passes', 'crosses',
                     'accurate_crosses', 'successful_tackles', 'fouls', 'offsides', 'yellow_cards', 'red_cards']

        return_value = []
        for col in col_names:
            return_value.append(col + '_1st')
            return_value.append(col + '_2nd')
        return return_value

    def team_comparison_title_to_col_name(self, title: str) -> str:
        return {
            'POSIADANIE PIŁKI %': 'possession',
            'STRZAŁY': 'shots',
            'CELNE STRZAŁY': 'shots_on_target',
            'RZUTY ROŻNE': 'corners',
            'PODANIA': 'passes',
            'PODANIA CELNE': 'accurate_passes',
            'DOŚRODKOWANIA': 'crosses',
            'DOŚRODKOWANIA CELNE': 'accurate_crosses',
            'ODBIORY UDANE': 'successful_tackles',
            'FAULE': 'fouls',
            'SPALONE': 'offsides',
            'ŻÓŁTE KARTKI': 'yellow_cards',
            'CZERWONE KARTKI': 'red_cards'
        }[title.upper()]

    def load_matches_data_for_round(self, number_of_clicks) -> pd.DataFrame:
        match_results = WebDriverWait(self.driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'app-league-widget-schedule:first-of-type '
                                                                  'app-league-widget-schedule-match '
                                                                  '.theme-gradient.cursor-pointer')))

        number_of_matches = len(match_results)
        df = pd.DataFrame()
        for i in range(number_of_matches):
            for index in range(number_of_clicks):
                self.change_round()

            data_row = {}
            # assign empty values to let python know what columns we have
            for name in self.get_column_names():
                data_row[name] = float("nan")

            round_header = self.driver.find_element(By.CSS_SELECTOR, 'app-league-widget-schedule:first-of-type '
                                                                     'span.text-center')
            round_title = round_header.get_attribute("innerText")
            round_number = round_title.split('.')[0]
            self.round = round_number

            match_results = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'app-league-widget-schedule:first-of-type '
                                                                      'app-league-widget-schedule-match '
                                                                      '.theme-gradient.cursor-pointer')))

            # redirect to match details
            match_results[i].click()

            match_header = WebDriverWait(self.driver, 5).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'app-upcoming-match-highlight '
                                                                      'span.flex.justify-end.uppercase.hidden'))
            )

            data_row['team_1st'] = match_header[0].get_attribute("innerText")
            data_row['team_2nd'] = match_header[1].get_attribute("innerText")

            match_score = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR,
                                            'app-upcoming-match-highlight .mx-2.py-4.text-center.text-white.theme-gradient span'))
            )

            match_score_text = match_score.get_attribute('innerText')
            data_row['score_1st'] = int(match_score_text.split(':')[0])
            data_row['score_2nd'] = int(match_score_text.split(':')[1])

            statistics_button = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'app-section '
                                                             'tui-tabs '
                                                             'button:nth-child(3)')))

            # move to subpage with statistics about considered match

            statistics_button.click()
            try:
                comparisons = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'app-teams-comparison-bar')))
            except TimeoutException:
                print("DATA IN THIS MATCH NOT FOUND", i, data_row)
                df = pd.concat([df, pd.DataFrame(data_row, index=[0])])
                self.driver.back()
                continue

            # there are 13 statistics (for each team) about a match which should be present in 'comparisons'

            col_names = self.get_column_names()
            for comp in comparisons:
                soup = BeautifulSoup(comp.get_attribute("innerHTML"), features="html.parser")
                spans = soup.find_all('span', {'class': ['text-cyan', 'text-2xl']})
                comparison_title = soup.select_one('div.w-full.px-4.text-center span')
                title_text = BeautifulSoup.get_text(comparison_title)
                col_name_from_title = self.team_comparison_title_to_col_name(title_text)
                # set result for the first team
                data_row[f"{col_name_from_title}_1st"] = BeautifulSoup.get_text(spans[0])

                # set result for the second team
                data_row[f"{col_name_from_title}_2nd"] = BeautifulSoup.get_text(spans[1])

            df = pd.concat([df, pd.DataFrame(data_row, index=[0])])
            self.driver.back()

        return df

    def change_round(self, attempt=0) -> None:
        attempt += 1
        if attempt > 5:
            print("Too many tries to change Round!")
            return
        try:
            round_changer = WebDriverWait(self.driver, 5) \
                .until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, 'app-league-widget-schedule:first-of-type tui-svg')))
            round_changer.click()
        except ElementClickInterceptedException:
            print('round change failed. I will try again. Nr of attempt: ', attempt)
            self.change_round(attempt)

    def scrap_data(self) -> pd.DataFrame:
        self.driver.get('https://www.ekstraklasa.org/terminarz')
        self.driver.refresh()
        time.sleep(2)
        # close cookies dialog to prevent it from blocking clicking another element
        cookies_btn = WebDriverWait(self.driver, 2).until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[data'
                                                                                                       '-appearance '
                                                                                                       '="primary"]')))
        cookies_btn.click()

        # open seasons select
        element = self.driver.find_element(By.CSS_SELECTOR, 'input.t-input')
        element.click()

        # open particular season (navigating)
        list_elements = self.driver.find_elements(By.CSS_SELECTOR, 'tui-data-list button')
        list_elements[0].click()
        time.sleep(2)

        df = pd.DataFrame()
        while_index = 0
        while True:

            round_df = self.load_matches_data_for_round(while_index)
            while_index += 1
            df = pd.concat([df, round_df])

            if self.round == '1':
            #if while_index == 1:
                break

        print(df)
        return df

    def scrap_and_save(self) -> None:
        df = self.scrap_data()
        df.fillna('MISSING')
        df.to_csv(f'data_{self.seasons[self.season_number]}.csv', encoding='utf-8', index=False)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print('START')
    # scrap()
    scrapper = EkstraklasaScrapper(0)
    scrapper.scrap_and_save()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
