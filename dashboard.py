import time
import sys
import json
import os
import traceback

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys


class DashboardController:
    driver: webdriver.Chrome = None
    config_data = {}
    url = None
    autologin = None
    _windows = None

    def __init__(self, config_path, profile_dir=None):
        self.profile = os.path.basename(config_path).replace('.json', '')
        self.profile_dir = profile_dir or os.path.join(os.path.dirname(os.path.realpath(__file__)), 'profiles')
        if not os.path.exists(self.profile_dir):
            os.mkdir(self.profile_dir)
        self.config_path = config_path
        self.read_config()

    def read_config(self):
        with open(self.config_path, 'r') as fh:
            self.config_data = json.load(fh)
            self.url = self.config_data.get('url')
            self.autologin = self.config_data.get('autologin', {})
            self.use_css_selectors = self.config_data.get('use_css_selectors', False)
            self.require_actual = self.config_data.get('require_actual', None)

    def save_config(self):
        with open(self.config_path, 'w') as fh:
            json.dump(self.config_data, fh, indent=2)
        self.read_config()

    def create_driver(self):
        chrome_options = Options()
        chrome_options.add_argument('--disable-infobars')
        if self.config_data.get('fullscreen', False) is True:
            chrome_options.add_argument('--start-fullscreen')
        chrome_options.add_argument('--user-data-dir={}'.format(os.path.join(self.profile_dir, self.profile)))
        resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources', 'chromedriver.exe')
        self.driver = webdriver.Chrome(executable_path=resources_dir, chrome_options=chrome_options)
        self._windows = []+self.driver.window_handles

    def destroy_driver(self):
        self.driver.close()

    def check_windows(self):
        return self.driver.window_handles == self._windows

    def check_enforce(self):
        if self.require_actual is not None:
            try:
                for el in self.driver.find_elements_by_css_selector(self.require_actual):
                    return True
            except Exception:
                return False
        else:
            return self.driver.current_url == self.url

    def enforce_url(self):
        if not self.check_enforce():
            print('Navigating to {}'.format(self.url))
            self.driver.get(self.url)
            time.sleep(2)
            if self.autologin:
                el = None
                for key in self.autologin:
                    if self.use_css_selectors:
                        try:
                            for el in self.driver.find_elements_by_css_selector(key):
                                el.send_keys(self.autologin[key])
                        except NoSuchElementException:
                            print('Could no find element: {}'.format(key))
                            continue
                    else:
                        try:
                            el = self.driver.find_element_by_id(key)
                            el.send_keys(self.autologin[key])
                        except NoSuchElementException:
                            continue

                if el is not None:
                    print('Found at least one element of autologin, submitting')
                    el.send_keys(Keys.RETURN)
                    self.driver.implicitly_wait(3)
                    if not self.check_enforce():
                        self.driver.get(self.url)

    def restore_window_position(self):
        position = self.config_data.get('position', {'x': 10, 'y':10})
        print('Restoring window position: {x}, {y}'.format(**position))
        self.driver.set_window_position(position['x'], position['y'])
        while True:
            try:
                body = self.driver.find_element_by_tag_name('body')
                if body:
                    body.send_keys(Keys.F11)
                    break
            except NoSuchElementException:
                continue

    def save_window_position(self):
        if self.check_windows():
            position = self.driver.get_window_position()
            self.config_data['position'] = position
            self.save_config()

    def loop(self):
        self.create_driver()
        self.enforce_url()
        if self.config_data.get('restore', False) is True:
            self.restore_window_position()
        if self.config_data.get('maximize', False) is True:
            self.driver.maximize_window()
        while True:
            time.sleep(0.5)
            self.enforce_url()
            self.save_window_position()


def main():
    os.chdir(os.path.dirname(__file__))

    config_path = None
    config_dir = os.path.join(os.path.dirname(__file__), 'configs')

    if not os.path.exists(config_dir):
        os.mkdir(config_dir)

    config_list = list(os.listdir(config_dir))
    config_list.sort()
    for fn in config_list:
        if fn.endswith('.json'):
            if len(sys.argv) > 1:
                if fn in sys.argv or fn.replace('.json', '') in sys.argv:
                    config_path = os.path.join(config_dir, fn)
            else:
                print('Loading first config we could find: {}'.format(fn))
                config_path = os.path.join(config_dir, fn)
        if config_path is not None:
            break

    if not config_path:
        print('You should create a config under: {}'.format(config_dir))
        sys.exit(1)

    if not os.path.exists(config_path):
        print('Config does not exist: %s', config_path)
        sys.exit(1)

    while True:
        try:
            cc = DashboardController(config_path)
            cc.loop()
        except:
            tb_str = traceback.format_exc()
            if 'chrome not reachable' in tb_str or 'not found' in tb_str:
                print('Chrome disappeared')
            else:
                traceback.print_exc()
        try:
            cc.destroy_driver()
        except:
            pass

        if '--loop' in sys.argv:
            print('Will try again in 5 seconds')
            time.sleep(5)
            continue
        else:
            break

if __name__ == "__main__":
    main()
