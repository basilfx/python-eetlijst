from bs4 import BeautifulSoup

from datetime import datetime, timedelta

import requests
import urlparse
import re

BASE_URL = "http://www.eetlijst.nl/"

TIMEOUT_SESSION = 60 * 5
TIMEOUT_CACHE = 60 * 5 / 2

RE_JAVASCRIPT_VS_1 = re.compile(r"javascript:vs")
RE_JAVASCRIPT_VS_2 = re.compile(r"javascript:vs\(([0-9]*)\);")
RE_JAVASCRIPT_K = re.compile(r"javascript:k\(([0-9]*),([-0-9]*),([-0-9]*)\);")
RE_RESIDENTS = re.compile("Meer informatie over")

def timeout(seconds):
    """
    Helper to calculate datetime for now plus some seconds.
    """
    return datetime.now() + timedelta(seconds=seconds)

class Error(Exception):
    """
    Base Eetlijst error.
    """
    pass

class LoginError(Error):
    """
    Error class for bad logins.
    """
    pass

class SessionError(Error):
    """
    Error class for session and/or other errors.
    """
    pass

class StatusRow(object):
    """
    """

    __slots__ = ["timestamp", "deadline", "statuses"]

    def __init__(self, timestamp, deadline, statuses):
        self.timestamp = timestamp
        self.deadline = deadline
        self.statuses = statuses

    def has_deadline_passed(self):
        return self.timestamp < datetime.now() if self.deadline else False

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
    """
    """

    __slots__ = ["username", "password", "session", "cache"]

    def __init__(self, username, password, login=False):
        """
        Construct a new Eetlijst object. By default, login is deferred until
        the first action is executed.
        """

        self.username = username
        self.password = password

        self.session = None
        self.cache = {}

        # Login if applicable.
        if login:
            self._get_session()

    def clear_cache(self):
        """
        Clear the internal cache and reset session.
        """

        self.session = None
        self.cache = {}

    def get_session_id(self):
        """
        Return the current session id. If not session id is not available, then
        None will be returned.
        """

        return self._get_session()

    def get_name(self):
        """
        Get the name of the Eetlijst list.
        """

        response = self._main_page()

        # Grap the list name
        soup = self._get_soup(response.content)
        return soup.find(["head", "title"]).text.replace("Eetlijst.nl - ", "", 1).strip()

    def get_residents(self):
        """
        Return all users listed on the Eetlijst list. It does not account for
        users that have been deleted.
        """

        response = self._main_page()

        # Find all names
        soup = self._get_soup(response.content)
        residents = soup.find_all(["th", "a"], title=RE_RESIDENTS)
        return [ x.nobr.b.text for x in residents ]

    def get_noticeboard(self):
        """
        Return the contents of the noticeboard. It removes any formatting and/or
        links.
        """

        response = self._main_page()

        # Grap the notice board
        soup = self._get_soup(response.content)
        return soup.find("a", title="Klik hier als je het prikbord wilt aanpassen").text

    def set_noticeboard(self, message):
        """
        Update the contents of the noticeboard.
        """

        self._main_page(post=True, data={ "messageboard": message })

    def get_statuses(self, limit=None):
        """
        Return the diner status of the residents for one or multiple days.
        """

        response = self._main_page()

        # Grap the statuses
        soup = self._get_soup(response.content)
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
            if limit is not None and i >= limit:
                break

            # Skip header rows
            if len(row.find_all("th")) > 0:
                continue

            # Check for deadline
            if i == 0:
                has_deadline = len(row.find(["td", "a"], href=RE_JAVASCRIPT_VS_1) or []) == 1

            if has_deadline:
                start = 2
                pattern = RE_JAVASCRIPT_VS_2
            else:
                start = 1
                pattern = RE_JAVASCRIPT_K

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
                cell = cell.text()
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

            results.append(StatusRow(timestamp=timestamp, deadline=has_deadline, statuses=statuses))
            i = i + 1

        return results

    def _get_soup(self, content):
        return BeautifulSoup(content, "html.parser")

    def _from_cache(self, key):
        try:
            response, valid_until = self.cache[key]
        except KeyError:
            return None

        return response if datetime.now() < valid_until else None

    def _login(self):
        # Create request
        payload = { "login": self.username, "pass": self.password }
        response = requests.get(BASE_URL + "login.php", params=payload)

        # Check for errors
        if response.status_code != 200:
            raise SessionError("Unexpected status code: %d" % response.status_code)

        if "r=failed" in response.url:
            raise LoginError("Unable to login. Username and/or password incorrect.")

        # Get session parameter
        query_string = urlparse.urlparse(response.url).query
        query_array = urlparse.parse_qs(query_string)

        self.session = (query_array.get("session_id"), timeout(seconds=TIMEOUT_SESSION))

        # Login redirects to main page, so cache it
        self.cache["main_page"] = (response, timeout(seconds=TIMEOUT_CACHE))

    def _get_session(self, is_retry=False, renew=True):
        # Start a session
        if self.session is None:
            if not renew:
                return

            self._login()

        # Check if session is still valid
        session, valid_until = self.session

        if valid_until < datetime.now():
            if not renew:
                return

            if is_retry:
                raise SessionError("Unable to renew session.")
            else:
                self.session = None
                return self._get_session(is_retry=True)

        return session[0]

    def _main_page(self, is_retry=False, data={}, post=False):
        # Prepare request
        if post:
            payload = {
                "session_id": self._get_session(),
                "messageboard": "",
                "veranderdag": "",
                "nieuwetijd": "",
                "submittype": 2,
                "who": -1,
                "what": -1,
                "day": []
            }
            payload.update(data)

            response = requests.post(BASE_URL + "main.php", data=payload)
        else:
            payload = { "session_id": self._get_session() }
            payload.update(data)

            response = self._from_cache("main_page") or requests.get(BASE_URL + "main.php", params=payload)

        # Check for errors
        if response.status_code != 200:
            raise SessionError("Unexpected status code: %d" % response.status_code)

        # Session expired
        if "login.php" in response.url:
            self.clear_cache()

            # Determine to retry or not
            if is_retry:
                raise SessionError("Unable to retrieve page: main.php")
            else:
                return self._main_page(is_retry=True, data=data, post=post)

        # Update cache and session
        self.session = (self.session[0], timeout(seconds=TIMEOUT_SESSION))
        self.cache["main_page"] = (response, timeout(seconds=TIMEOUT_CACHE))

        return response