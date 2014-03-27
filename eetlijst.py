from bs4 import BeautifulSoup
from datetime import datetime, timedelta

import requests
import urlparse
import collections
import re

JAVASCRIPT_VS_1 = re.compile("javascript:vs")
JAVASCRIPT_VS_2 = re.compile(r"javascript:vs\(([0-9]*)\);")
JAVASCRIPT_K = re.compile(r"javascript:k\(([0-9]*),([-0-9]*),([-0-9]*)\);")

def timeout(minutes):
    return datetime.now() + timedelta(seconds=60 * minutes)

class EetlijstException(Exception):
    pass

class EetlijstStatusRow(object):
    def __init__(self, timestamp, has_deadline, statuses):
        self.timestamp = timestamp
        self.has_deadline = has_deadline
        self.statuses = statuses

    def has_deadline_passed(self):
        return self.timestamp < datetime.now() if self.has_deadline else False

    def has_cook(self):
        for value in self.statuses.itervalues():
            if value > 0:
                return True

        return False

    def has_diner_guests(self):
        for value in self.statuses.itervalues():
            if value < 0 and not value == -5:
                return True

        return False

    def get_cooks(self):
        result = []

        for key, value in self.statuses.iteritems():
            if value > 0:
                result.append((key, value - 1))

        return result

    def get_nones(self):
        result = []

        for key, value in self.statuses.iteritems():
            if value == 0:
                result.append((key, 0))

        return result

    def get_diner_guests(self):
        result = []

        for key, value in self.statuses.iteritems():
            if value < 0 and not value == -5:
                result.append((key, -1 * value - 1))

        return result

class Eetlijst(object):
    def __init__(self, username, password):
        self.username = username
        self.password = password

        self.session = None
        self.cache = {}

    def clear_cache(self):
        self.cache = {}

    def is_valid_login(self):
        if self.session is None:
            return not self._login() == False
        else:
            return self.session != False

    def get_name(self):
        response = self._main_page()

        # Grap the list name
        soup = BeautifulSoup(response.content, "html.parser")
        return soup.find(["head", "title"]).replace("Eetlijst.nl - ", "")

    def get_residents(self):
        response = self._main_page()

        # Find all names
        soup = BeautifulSoup(response.content, "html.parser")
        residents = soup.find_all(["th", "a"], title=re.compile("Meer informatie over"))
        return [ str(x.nobr.b.text) for x in residents ]

    def get_notice_board(self):
        response = self._main_page()

        # Grap the notice board
        soup = BeautifulSoup(response.content, "html.parser")
        return str(soup.find("a", title="Klik hier als je het prikbord wilt aanpassen").text)

    def get_statuses(self, limit=None):
        response = self._main_page()

        # Grap the statuses
        soup = BeautifulSoup(response.content, "html.parser")
        start = soup.find(["table", "tbody", "tr", "th"], width="80")

        if not start:
            return None

        # Grap the table
        rows = start.parent.parent.find_all("tr")

        # Other initialisation
        has_deadline = False
        pattern = None
        results = []
        start = 0
        i = 0

        for row in rows:
            # Check for limit
            if not limit is None and i >= limit:
                break

            # Skip header rows
            if len(row.find_all("th")) > 0:
                continue

            # Check for deadline
            if i == 0:
                has_deadline = len(row.find(["td", "a"], href=JAVASCRIPT_VS_1) or []) == 1

            if has_deadline:
                start = 2
                pattern = JAVASCRIPT_VS_2
            else:
                start = 1
                pattern = JAVASCRIPT_K

            # Match deadline
            matches = re.search(pattern, str(row))
            timestamp = datetime.fromtimestamp(int(matches.group(1)))
            statuses = {}
            index = 0

            for cell in row.find_all("td"):
                index = index + 1
                if not index > start:
                    continue

                # Count statuses
                cell = str(cell)
                nop = cell.count("nop.gif")
                kook = cell.count("kook.gif")
                eet = cell.count("eet.gif")
                leeg = cell.count("leeg.gif")

                # Get the resident index
                resident = index - start - 1

                # Set the data
                if nop > 0:
                    statuses[resident] = 0;
                elif kook > 0 and eet == 0:
                    statuses[resident] = kook;
                elif kook > 0 and eet > 0:
                    statuses[resident] = kook + eet;
                elif eet > 0:
                    statuses[resident] = -1 * eet;
                elif leeg > 0:
                    statuses[resident] = -5;

            results.append(EetlijstStatusRow(timestamp=timestamp, has_deadline=has_deadline, statuses=statuses))
            i = i + 1

        # Done
        return results

    def _login(self):
        # Make request
        payload = { "login": self.username, "pass": self.password }
        response = requests.get("http://www.eetlijst.nl/login.php", params=payload)

        # Check for errors
        if response.status_code != 200:
            raise EetlijstException("Unexpected status code: %d" % response.status_code)

        if "r=failed" in response.url:
            self.session = False
            return False

        # Get session parameter
        query_string = urlparse.urlparse(response.url).query
        query_array = urlparse.parse_qs(query_string)

        self.session = (query_array.get("session_id", False), timeout(minutes=5))

        # Done
        return True

    def _get_session(self, is_retry=False):
        if self.session is None:
            self._login()

        # Check if login and/or password invalid
        if self.session == False:
            raise EetlijstException("Unable to login.")

        # Check if session is still valid
        session, valid_until = self.session

        if valid_until < datetime.now():
            if not is_retry:
                self.session = None
                return self._get_session(is_retry=True)
            else:
                raise EetlijstException("Unable to renew session.")

        # Done
        return session

    def _main_page(self, is_retry=False):
        # Return from cache if possible
        if "main_page" in self.cache:
            response, valid_until = self.cache["main_page"]

            if datetime.now() < valid_until:
                return response

        # Make request
        payload = { "session_id": self._get_session() }
        response = requests.get("http://www.eetlijst.nl/main.php", params=payload)

        # Check for errors
        if response.status_code != 200:
            raise EetlijstException("Unexpected status code: %d" % response.status_code)

        if "login.php" in response.url:
            # Unset data
            self.session = None
            del self.cache["main_page"]

            # Determine to retry or not
            if is_retry:
                raise EetlijstException("Unable to retrieve page: main.php")
            else:
                return self._main_page(is_retry=True)

        # Done
        self.cache["main_page"] = (response, timeout(minutes=5))
        return response