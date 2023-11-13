import _io
import contextlib
import json
import os
import re
import time
import warnings
from pprint import pprint
from urllib.parse import urljoin
from urllib.parse import urlparse

import pandas as pd
import requests
import requests.exceptions
from bs4 import BeautifulSoup
from requests import Session, Response
from urllib3.exceptions import InsecureRequestWarning
import validators

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

User = Session()
User.headers.update({
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/35.0.1916.47 Safari/537.36'})


def to_soup(input_object: str | bytes | requests.models.Response | _io.TextIOWrapper,
            parser_type: str = 'html.parser') -> BeautifulSoup:
    """
    Returns a BeautifulSoup object from a string, file, or file-like object.

    :param str | bytes | requests.models.Response | _io.TextIOWrapper input_object:
        Object to be turned to BS.
    :param str parser_type: set a type of parser you want to use
           ("lxml", "lxml-xml", "html.parser", or "html5lib")
    :return: BeautifulSoup object.
    """
    if isinstance(input_object, _io.TextIOWrapper):
        return BeautifulSoup(input_object, features=parser_type)
    elif isinstance(input_object, requests.models.Response):
        return BeautifulSoup(input_object.content, parser_type)
    elif isinstance(input_object, bytes):
        return BeautifulSoup(input_object, features=parser_type)
    elif isinstance(input_object, str):
        with open(input_object, 'r', encoding='utf-8', errors='ignore') as f:
            return BeautifulSoup(f, features=parser_type)
    elif validators.url(input_object):
        get_data = User.get(input_object)
        return BeautifulSoup(get_data.content, features=parser_type)
    return BeautifulSoup()


def save_page(url: str, filename: str, session=None, allow_redirects=True):
    """
    Saves a web-page_response as an HTML-file.

    :param str url: Link to the page_response to be saved.
    :param str filename: Full name of the file to be saved.
    :param session: To pass a session object. If not passed, a new session is created.
    :param bool allow_redirects: Indicates whether redirects are allowed. Default is True.
    :return bool: Result of the saving page_response.
        True if the page_response was saved successfully, False otherwise.
    """
    if not (url_check := validators.url(url)):
        raise ValueError(f'{url} is not a valid URL.')
    if session is None:
        session = User
    try:
        page_response = session.get(url, allow_redirects=allow_redirects)
    except (requests.exceptions.TooManyRedirects,
            requests.exceptions.ConnectionError) as error:
        page_response = requests.Response()
        page_response.status_code = error
    except requests.exceptions.SSLError:
        page_response = session.get(url, allow_redirects=True, verify=False)
    if page_response.status_code in {200, 301, 302}:
        s = to_soup(page_response.content, 'link')
        full_name = filename if '.' in filename else f'{filename}.html'
        with open(full_name, 'w', encoding='utf-8') as file:
            file.write(s.prettify())
        return True
    else:
        print(f'Error {page_response.status_code}\ncaused by by URL: {url}')
        return False


def create_folder(name, path=None):
    if path:
        os.chdir(path)
    try:
        os.makedirs(name)
    except FileExistsError:
        pass
    try:
        os.chdir(name)
        return f'{os.getcwd()}/'
    except FileNotFoundError and OSError:
        return -1


class Parser:
    """
    A class to find and download page from a search page of a web-site.
    """

    def __init__(self,
                 url: str,
                 file_path: str = os.getcwd(),
                 ):
        """
        Constructor.

        :param str url: url of search page, place for article should be replaces with XXXX
                    for example, 'https://www.example.com/search/?q=XXXX'
        """
        self.user = User
        self.search_url = url
        self.file_path = file_path
        # get domain from 'self.search_url' str
        self.domain = '{uri.netloc}'.format(uri=urlparse(self.search_url))
        # get base url from 'self.search_url' str
        self.host = '{uri.scheme}://{uri.netloc}' \
            .format(uri=urlparse(self.search_url))
        self.html_file_path = create_folder('html', file_path) + '/'

    def parser(self,
               search_input: str,
               redirect: bool,
               pattern_search: list[str, dict],
               ab: list[str],
               post_request: bool = False,
               headers: dict = None,
               wait_time: int = 2,
               ):
        """
        Finds needed pages on a website and downloads them.

        :param str search_input: Absolute path of the CSV file OR filename if the file
                is in self.file_path folder, containing a list of search terms and
                corresponding identifications, separated by commas.
        :param bool redirect: allows to redirect page after connecting to 'url'
        :param list[str, dict] pattern_search: set tag and it's parameters which used to find a link
                to a product in the search page
        :param list[str] ab: set a tag and it's parameter, which used to find a link
                in pattern_search tag (typically ['a', 'href'])
        :param bool post_request: To make POST request to 'url' instead of GET.
                Default is False.

        :param dict headers: To pass cookies.
        :param int wait_time: Waiting time between each request.

        """
        # print('++-> ""def parser""<-++')
        self.html_file_path = create_folder('html', self.file_path)
        os.chdir(self.file_path)

        data_all = []
        if not os.path.isfile(search_input):
            raise TypeError(f'Unrecognized parameter "search_input":\n{search_input}')

        # putting all search terms from CSV file to one variable 'art_ids_data'
        with open(search_input, "r") as articles:
            art_ids_data = {}
            for line in articles:
                art, identification = line.rstrip().split(',')
                # formatting strings
                for x in ['"', '\n']:
                    art = art.replace(x, '').strip()
                    identification = identification.replace(x, '').strip()
                art_ids_data[identification] = art

        if headers:
            self.user.headers.update(headers)
        else:
            self.user.headers.update({
                'domain': self.domain})

        # Starting to iterate over all search terms
        for identification, art in art_ids_data.items():
            identification, art = identification.replace('"', ''), art.replace('"', '')
            data_product = {'Article': art, 'SKU': identification}
            # new url with search term in it
            url = self.search_url.replace('XXXX', art)
            if post_request:
                post_request = {
                    'keywords': art,
                    'submit': 'Search'}
                search_page = self.user.post(url, data=post_request)
            else:
                # Trying 5 times to connect to the url
                search_page = None
                error = 0
                while error < 5:
                    try:
                        search_page = self.user.get(url, allow_redirects=True)
                        error = 5
                    except (requests.exceptions.SSLError,
                            requests.exceptions.ConnectionError):
                        time.sleep(wait_time)
                        error += 1
            if search_page is None:
                raise ValueError(f'Error while connecting to {url}.')

            print(art, search_page.status_code)
            data_product['search status'] = search_page.status_code

        return data_all


if __name__ == "__main__":
    pass
