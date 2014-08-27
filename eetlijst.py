# Unofficial Python API to interface with Eetlijst.nl
# Copyright (C) 2014 Bas Stottelaar

# See the LICENSE file for the full GPLv3 license

from bs4 import BeautifulSoup

from datetime import datetime, timedelta

import requests
import urlparse
import time
import re

BASE_URL = "http://www.eetlijst.nl/"

TIMEOUT_SESSION = 60 * 5
TIMEOUT_CACHE = 60 * 5 / 2

RE_DIGIT = re.compile("\d+")
RE_JAVASCRIPT_VS_1 = re.compile(r"javascript:vs")
RE_JAVASCRIPT_VS_2 = re.compile(r"javascript:vs\(([0-9]*)\);")
RE_JAVASCRIPT_K = re.compile(r"javascript:k\(([0-9]*),([-0-9]*),([-0-9]*)\);")
RE_RESIDENTS = re.compile(r"Meer informatie over")
RE_LAST_CHANGED = re.compile(r"onveranderd sinds ([0-9]+):([0-9]+)")

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

class ScrapingError(Error):
    """
    Error class for scraping related errors.
    """
    pass

class Status(object):
    """
    Represent one cell in a row of the dinner status table. A status is a value,
    where:

    None -> Nothing set
     -N  -> Diner + N
     -1  -> Diner
      0  -> No dinner
     +1  -> Cook
     +N  -> Cook + N
    """

    __slots__ = ["value", "last_changed"]

    def __init__(self, value, last_changed):
        self.value = value
        self.last_changed = last_changed

    def __repr__(self):
        return "Status(value=%d, last_changed=%s)" % (self.value,
            self.last_changed)

class StatusRow(object):
    """
    Represent one row of the dinner status table. A status row has a timestamp,
    a deadline and a list of statuses (resident -> status).
    """

    __slots__ = ["timestamp", "deadline", "statuses"]

    def __init__(self, timestamp, deadline, statuses):
        self.timestamp = timestamp
        self.deadline = deadline
        self.statuses = statuses

    def __repr__(self):
        return "StatusRow(timestamp=%s, deadline=%s, statuses=%s)" % (
            self.timestamp, self.deadline, self.statuses)

    def has_deadline_passed(self):
        """
        Return True if the deadline has passed, False if not or if no deadline.
        """

        return self.deadline < datetime.now() if self.deadline else False

    def time_left(self):
        """
        Calculate the delta time between now and the deadline. May return a
        negative number. In this case, the deadline has passed. If no deadline
        is given, then midnight is taken.
        """

        timestamp = self.deadline or datetime(
            year=self.timestamp.year, month=self.timestamp.month,
            day=self.timestamp.day, hour=23, minute=59, second=59)

        return timestamp - datetime.now()

    def has_cook(self):
        """
        Return True if there is at least one cook
        """

        return self._test(lambda x: x.value > 0)

    def has_diners(self):
        """
        Return true if there is at least one diner (which isn't a cook)
        """

        return self._test(lambda x: x.value < 0 and x.value is not None)

    def get_cooks(self):
        """
        Return a list of indices of all cooks
        """

        return self._extract(lambda x: x.value > 0)

    def get_diners(self):
        """
        Return a list of indices of all diners (which aren't cooks)
        """

        return self._extract(lambda x: x.value < 0 and x.value is not None)

    def get_diners_and_cooks(self):
        """
        Return a list of indices of all diners and cooks.
        """

        return self.get_cooks() + self.get_diners()

    def get_nones(self):
        """
        Return a list of indices of ones not attending dinner.
        """

        return self._extract(lambda x: x.value == 0)

    def get_unknowns(self):
        """
        Return a list of indices of ones who haven't made choice yet
        """

        return self._extract(lambda x: x.value is None)

    def get_nones_and_unknowns(self):
        """
        Return a list of indices of ones not attending dinner and who haven't
        made a choice yet.
        """

        return self.get_nones() + self.get_unknowns()

    def get_count(self, indices=None):
        """
        Count the number of people attending dinner. This may include guests.

        Optionally, a list of indices can be passed to limit the result.
        """

        count = 0

        if indices is None:
            statuses = self.statuses
        else:
            statuses = [ self.statuses[index] for index in indices ]

        for status in statuses:
            value = status.value

            if value is not None:
                if value < 0:
                    count += -1 * value
                elif value > 0:
                    count += value

        return count

    def get_statuses(self, indices=None):
        """
        Return the statuses.

        Optionally, a list of indices can be passed to limit the result.
        """

        if indices is None:
            return self.statuses
        else:
            return [ self.statuses[index] for index in indices ]

    def _extract(self, test_func):
        result = []

        for index, status in enumerate(self.statuses):
            if test_func(status):
                result.append(index)

        return result

    def _test(self, test_func):
        for status in self.statuses:
            if test_func(status):
                return True

        return False

class Eetlijst(object):
    """
    Eetlijst base class.
    """

    __slots__ = ["username", "password", "session", "cache"]

    def __init__(self, username=None, password=None, session_id=None,
        login=False):
        """
        Construct a new Eetlijst object. By default, login is deferred until
        the first action is executed.

        A username and password should be given to construct a session. Setting
        login=True will directly login and get a session id. Additionally, a
        session_id can be given a id that is known to be valid. Having
        login=True in this case will test the session id.
        """

        if username is None and password is None and session_id is None:
            raise LoginError("No username/password or session id provided.")

        self.username = username
        self.password = password

        self.session = None
        self.cache = {}

        # Store given session id
        if session_id:
            self.session = (session_id, timeout(seconds=TIMEOUT_SESSION))

            if login:
                self._main_page()
        else:
            # Login if applicable
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

        return self._get_session(renew=False)

    def get_name(self):
        """
        Get the name of the Eetlijst list.
        """

        response = self._main_page()

        # Grap the list name
        soup = self._get_soup(response.content)
        return soup.find(["head", "title"]) \
            .text.replace("Eetlijst.nl - ", "", 1).strip()

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
        return soup.find("a",
            title="Klik hier als je het prikbord wilt aanpassen").text

    def set_noticeboard(self, message):
        """
        Update the contents of the noticeboard.
        """

        self._main_page(post=True, data={ "messageboard": message })

    def set_status(self, resident_index, status, timestamp):
        """
        Set the status for a given resident_index and timestamp in the future.
        The timestamp should point to an extact row in the Eetlijst list.
        """

        if timestamp < datetime.now():
            raise ValueError("Timestamp cannot be in the past")

        self._main_page(post=True, data={ "submittype": 0,
            "who": resident_index, "what": status,
            "day[]": time.mktime(timestamp.timetuple()) })

    def get_status(self, resident_index, timestamp):
        """
        Return the status for a given date in the future. The timestamp should
        point to an extact row in the Eetlijst list.
        """

        raise NotImplementedError("Method noty yet implemented")

    def get_statuses(self, limit=None):
        """
        Return the diner status of the residents for one or multiple days,
        starting today. The result is a list of StatusRows, where each row
        represents the Eetlijst list.
        """

        response = self._main_page()

        # Find the main table by first navigating to a unique cell.
        soup = self._get_soup(response.content)
        start = soup.find(["table", "tbody", "tr", "th"], width="80")

        if not start:
            raise ScrapingError("Cannot parse status table")

        rows = start.parent.parent.find_all("tr")

        # Iterate over each status row
        has_deadline = False
        pattern = None
        results = []
        start = 0

        for row in rows:
            # Check for limit
            if limit and len(results) >= limit:
                break

            # Skip header rows
            if len(row.find_all("th")) > 0:
                continue

            # Check if the list uses deadlines
            if len(results) == 0:
                has_deadline = bool(row.find(["td", "a"],
                    href=RE_JAVASCRIPT_VS_1))

            if has_deadline:
                start = 2
                pattern = RE_JAVASCRIPT_VS_2
            else:
                start = 1
                pattern = RE_JAVASCRIPT_K

            # Match date and deadline
            matches = re.search(pattern, row.renderContents())
            timestamp = datetime.fromtimestamp(int(matches.group(1)))
            deadline = timestamp if has_deadline else None

            # Parse each cell for diner status
            statuses = []

            for index, cell in enumerate(row.find_all("td")):
                if index < start:
                    continue

                # Count statuses
                images = cell.renderContents()

                nop = images.count("nop.gif")
                kook = images.count("kook.gif")
                eet = images.count("eet.gif")
                leeg = images.count("leeg.gif")

                # Match numbers, in case there are more than 4 images
                extra = RE_DIGIT.findall(cell.text)
                extra = int(extra[0]) if extra else 1

                # Parse last changed. This only works for the first row
                if len(results) == 0:
                    date = timestamp.date()
                    title = cell.find("img")["title"].lower()
                    matches = re.search(RE_LAST_CHANGED, title)

                    if matches:
                        hour, minute = matches.groups()
                        last_changed = datetime(year=date.year,
                            month=date.month, day=date.day, hour=int(hour),
                            minute=int(minute))
                    else:
                        last_changed = datetime(year=date.year,
                            month=date.month, day=date.day, hour=0, minute=0)
                else:
                    last_changed = None

                # Set the data
                if nop > 0:
                    value = 0
                elif kook > 0 and eet == 0:
                    value = kook
                elif kook > 0 and eet > 0:
                    value = kook + (eet * extra)
                elif eet > 0:
                    value = -1 * (eet * extra)
                elif leeg > 0:
                    value = None
                else:
                    raise ScrapingError("Cannot parse diner status")

                statuses.append(Status(value=value, last_changed=last_changed))

            results.append(StatusRow(timestamp=timestamp, deadline=deadline,
                statuses=statuses))

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
        # Verify username and password
        if self.username is None and self.password is None:
            raise LoginError("Cannot login without username/password.")

        # Create request
        payload = { "login": self.username, "pass": self.password }
        response = requests.get(BASE_URL + "login.php", params=payload)

        # Check for errors
        if response.status_code != 200:
            raise SessionError("Unexpected status code: %d" %
                response.status_code)

        if "r=failed" in response.url:
            raise LoginError("Unable to login. Username and/or " +
                "password incorrect.")

        # Get session parameter
        query_string = urlparse.urlparse(response.url).query
        query_array = urlparse.parse_qs(query_string)

        try:
            self.session = (query_array.get("session_id")[0],
                timeout(seconds=TIMEOUT_SESSION))
        except IndexError:
            raise ScrapingError("Unable to strip session id from URL")

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

        return session

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
                "day": [],
                "submitwithform.x": 20,
                "submitwithform.y": 20
            }
            payload.update(data)

            response = requests.post(BASE_URL + "main.php", data=payload)
        else:
            payload = { "session_id": self._get_session() }
            payload.update(data)

            response = self._from_cache("main_page") or requests.get(
                BASE_URL + "main.php", params=payload)

        # Check for errors
        if response.status_code != 200:
            raise SessionError("Unexpected status code: %d" %
                response.status_code)

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