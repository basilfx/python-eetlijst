# Unofficial Python API to interface with Eetlijst.nl
# Copyright (C) 2014-2022 Bas Stottelaar

# See the LICENSE file for the full GPLv3 license

import re
import urllib.parse as urlparse
from datetime import datetime, timedelta
from typing import Callable, Optional, Union

import pytz
import requests
from bs4 import BeautifulSoup

__version__ = "2.0.0"

BASE_URL = "https://www.eetlijst.nl/"

RE_DIGIT = re.compile(r"\d+")
RE_JAVASCRIPT_VS_1 = re.compile(r"javascript:vs")
RE_JAVASCRIPT_VS_2 = re.compile(r"javascript:vs\(([0-9]*)\);")
RE_JAVASCRIPT_K = re.compile(r"javascript:k\(([0-9]*),([-0-9]*),([-0-9]*)\);")
RE_RESIDENTS = re.compile(r"Meer informatie over")
RE_LAST_CHANGED = re.compile(r"onveranderd sinds ([0-9]+):([0-9]+)")

TIMEOUT_SESSION = 60 * 5
TIMEOUT_CACHE = 60 * 5 / 2

TZ_EETLIJST = pytz.timezone("Europe/Amsterdam")
TZ_UTC = pytz.timezone("UTC")


def now() -> datetime:
    """
    Return current datetime object with UTC timezone.
    """
    return datetime.now(tz=TZ_UTC)


def timeout(seconds) -> datetime:
    """
    Helper to calculate datetime for now plus some seconds.
    """
    return now() + timedelta(seconds=seconds)


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
    Represent one cell in a row of the dinner status table. A status is a
    value, where:

    None -> Nothing set
     -N  -> Diner + N
     -1  -> Diner
      0  -> No dinner
     +1  -> Cook
     +N  -> Cook + N
    """

    __slots__ = ("value", "last_changed")

    def __init__(self, value, last_changed) -> None:
        self.value = value
        self.last_changed = last_changed

    def __repr__(self) -> str:
        return "Status(value=%d, last_changed=%s)" % (self.value, self.last_changed)


class StatusRow(object):
    """
    Represent one row of the dinner status table. A status row has a timestamp,
    a deadline and a list of statuses (resident -> status).
    """

    __slots__ = ("timestamp", "deadline", "statuses")

    def __init__(self, timestamp, deadline, statuses) -> None:
        self.timestamp = timestamp
        self.deadline = deadline
        self.statuses = statuses

    def __repr__(self) -> str:
        return "StatusRow(timestamp=%s, deadline=%s, statuses=%s)" % (
            self.timestamp,
            self.deadline,
            self.statuses,
        )

    def has_deadline_passed(self) -> bool:
        """
        Return True if the deadline has passed, False if not or if no deadline.
        """

        return self.deadline < now() if self.deadline else False

    def time_left(self) -> timedelta:
        """
        Calculate the delta time between now and the deadline. May return a
        negative number. In this case, the deadline has passed. If no deadline
        is given, then midnight is taken.
        """

        timestamp = self.deadline or datetime(
            year=self.timestamp.year,
            month=self.timestamp.month,
            day=self.timestamp.day,
            hour=23,
            minute=59,
            second=59,
        )

        return timestamp - now()

    def has_cook(self) -> bool:
        """
        Return True if there is at least one cook
        """

        return self._test(lambda x: x.value > 0)

    def has_diners(self) -> bool:
        """
        Return true if there is at least one diner (which isn't a cook)
        """

        return self._test(lambda x: x.value < 0 and x.value is not None)

    def get_cooks(self) -> list[int]:
        """
        Return a list of indices of all cooks
        """

        return self._extract(lambda x: x.value > 0)

    def get_diners(self) -> list[int]:
        """
        Return a list of indices of all diners (which are not cooks)
        """

        return self._extract(lambda x: x.value < 0 and x.value is not None)

    def get_diners_and_cooks(self) -> list[int]:
        """
        Return a list of indices of all diners and cooks.
        """

        return self.get_cooks() + self.get_diners()

    def get_nones(self) -> list[int]:
        """
        Return a list of indices of ones not attending dinner.
        """

        return self._extract(lambda x: x.value == 0)

    def get_unknowns(self) -> list[int]:
        """
        Return a list of indices of ones who haven't made choice yet
        """

        return self._extract(lambda x: x.value is None)

    def get_nones_and_unknowns(self) -> list[int]:
        """
        Return a list of indices of ones not attending dinner and who haven't
        made a choice yet.
        """

        return self.get_nones() + self.get_unknowns()

    def get_count(self, indices=None) -> int:
        """
        Count the number of people attending dinner. This may include guests.

        Optionally, a list of indices can be passed to limit the result.
        """

        count = 0

        if indices is None:
            statuses = self.statuses
        else:
            statuses = [self.statuses[index] for index in indices]

        for status in statuses:
            value = status.value

            if value is not None:
                if value < 0:
                    count += -1 * value
                elif value > 0:
                    count += value

        return count

    def get_statuses(self, indices=None) -> list[int]:
        """
        Return the statuses.

        Optionally, a list of indices can be passed to limit the result.
        """

        if indices is None:
            return self.statuses
        else:
            return [self.statuses[index] for index in indices]

    def _extract(self, test_func: Callable[[int], bool]) -> list[int]:
        result = []

        for index, status in enumerate(self.statuses):
            if test_func(status):
                result.append(index)

        return result

    def _test(self, test_func: Callable[[int], bool]) -> bool:
        for status in self.statuses:
            if test_func(status):
                return True

        return False


class Eetlijst(object):
    """
    Eetlijst base class.
    """

    __slots__ = ("username", "password", "session", "cache")

    def __init__(
        self,
        username: str = None,
        password: str = None,
        session_id: str = None,
        login: bool = False,
    ) -> None:
        """
        Construct a new Eetlijst client. By default, login is deferred until
        the first action is executed.

        A username and password should be given to construct a session. Setting
        `login` to `True` will directly login and get a session id.
        Additionally, a `session_id` can be set to an identifier that is known
        to be valid. Having `login` set to `True` in this case will test the
        session identifier.

        One big fat warning: this API is prone to race conditions. For
        instance, reading data, wait a few seconds and writing it back may go
        wrong if data has changed via other requests in the mean time.
        Unfortunately, there is not much that you can do about it.
        """

        if username is None and password is None and session_id is None:
            raise LoginError("No username/password or session identifier provided.")

        self.username = username
        self.password = password

        self.session = None
        self.cache = {}

        # Store given session identifier.
        if session_id:
            self.session = (session_id, timeout(seconds=TIMEOUT_SESSION))

            if login:
                self._main_page()
        else:
            # Login if applicable.
            if login:
                self._get_session()

    def clear_cache(self) -> None:
        """
        Clear the internal cache and reset session.
        """

        self.session = None
        self.cache = {}

    def get_session_id(self) -> str:
        """
        Return the current session identifier. If not session identifier is
        not available, then `None` will be returned.
        """

        return self._get_session(renew=False)

    def get_name(self) -> str:
        """
        Get the name of the Eetlijst list.
        """

        content = self._main_page()

        # Grap the list name.
        soup = self._get_soup(content)
        return (
            soup.find(["head", "title"]).text.replace("Eetlijst.nl - ", "", 1).strip()
        )

    def get_residents(self) -> list[str]:
        """
        Return all users listed on the Eetlijst list. It does not account for
        users that have been deleted.
        """

        content = self._main_page()

        # Find all names.
        soup = self._get_soup(content)
        residents = soup.find_all(["th", "a"], title=RE_RESIDENTS)
        return [x.nobr.b.text for x in residents]

    def get_noticeboard(self) -> str:
        """
        Return the contents of the noticeboard. It removes any formatting
        and/or links.
        """

        content = self._main_page()

        # Grap the notice board.
        soup = self._get_soup(content)
        return soup.find("a", title="Klik hier als je het prikbord wilt aanpassen").text

    def set_noticeboard(self, message: str) -> None:
        """
        Update the contents of the noticeboard.
        """

        self._main_page(
            post=True,
            data={
                "Aanpassen.x": 20,
                "Aanpassen.y": 20,
                "messageboard": message,
            },
        )

    def set_status(self, resident_index, value, timestamp) -> str:
        """
        Set the status for a given resident_index and timestamp in the future.
        The timestamp should point to an extact row in the Eetlijst list.
        """

        if timestamp.tzinfo is None:
            raise ValueError("Timestamp is time zone unaware.")

        if timestamp < now():
            raise ValueError("Timestamp cannot be in the past.")

        # Pick strategy for advancing to value. Values other than -5, -4 and 4
        # can be set without a problem, but the rest may require multiple
        # steps.
        def _request(what):
            self._main_page(
                post=True,
                data={
                    "day[]": int(timestamp.timestamp()),
                    "submittype": 0,
                    "submitwithform.x": 20,
                    "submitwithform.y": 20,
                    "what": what,
                    "who": resident_index,
                },
            )

        if value == -5:
            _request(-3)
            _request(-4)
            _request(-4)
        elif value == -4:
            _request(-3)
            _request(-4)
        elif value == 4:
            _request(3)
            _request(4)
        elif value is None:
            _request(-5)  # None corresponds to -5.
        else:
            _request(value)

        # TODO: add verification. Probably something like:
        # self.get_status(resident_index, timestamp) == value

    def get_status(self, resident_index: int, timestamp: datetime) -> int:
        """
        Return the status for a given date in the future. The timestamp should
        point to an extact row in the Eetlijst list.
        """

        if timestamp.tzinfo is None:
            raise ValueError("Timestamp is time zone unaware.")

        if timestamp < now():
            raise ValueError("Timestamp cannot be in the past.")

        raise NotImplementedError("Method not yet implemented.")

    def get_statuses(self, limit: Optional[int] = None) -> list[StatusRow]:
        """
        Return the diner status of the residents for one or multiple days,
        starting today. The result is a list of StatusRows, where each row
        represents the Eetlijst list.
        """

        content = self._main_page()

        # Find the main table by first navigating to a unique cell.
        soup = self._get_soup(content)
        start = soup.find(["table", "tbody", "tr", "th"], width="80")

        if not start:
            raise ScrapingError("Cannot parse status table.")

        rows = start.parent.parent.find_all("tr")

        # Iterate over each status row.
        has_deadline = False
        pattern = None
        results = []
        start = 0

        for row in rows:
            # Check for limit.
            if limit and len(results) >= limit:
                break

            # Skip header rows.
            if len(row.find_all("th")) > 0:
                continue

            # Check if the list uses deadlines.
            if len(results) == 0:
                has_deadline = bool(row.find(["td", "a"], href=RE_JAVASCRIPT_VS_1))

            if has_deadline:
                start = 2
                pattern = RE_JAVASCRIPT_VS_2
            else:
                start = 1
                pattern = RE_JAVASCRIPT_K

            # Match date and deadline.
            matches = re.search(pattern, row.decode_contents())
            timestamp = datetime.fromtimestamp(int(matches.group(1)), tz=TZ_UTC)
            timestamp_eetlijst = timestamp.astimezone(TZ_EETLIJST)

            # Parse each cell for diner status.
            statuses = []

            for index, cell in enumerate(row.find_all("td")):
                if index < start:
                    continue

                # Count statuses
                images = cell.decode_contents()

                nop = images.count("nop.gif")
                kook = images.count("kook.gif")
                eet = images.count("eet.gif")
                leeg = images.count("leeg.gif")

                # Match numbers, in case there are more than 4 images.
                extra = RE_DIGIT.findall(cell.text)
                extra = int(extra[0]) if extra else 1

                # Parse last changed. This only works for the first row. Note
                # that Eetlijst.nl is a Dutch website and displays time in
                # Europe/Amsterdam. Because time conversion is buggy, we take
                # the UTC midnight, subtract the difference with
                # Europe/Amsterdam for that day, and then add the hours and
                # minutes to it. For some reason, converting Europe/Amsterdam
                # back to UTC fails (see question at
                # http://stackoverflow.com/a/5801263/1423623 for more info).
                if len(results) == 0:
                    midnight = (
                        timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                        - timestamp_eetlijst.utcoffset()
                    )
                    matches = re.search(RE_LAST_CHANGED, cell.decode_contents().lower())

                    if matches:
                        hour, minute = matches.groups()
                        last_changed = midnight + timedelta(
                            seconds=int(hour) * 3600 + int(minute) * 60
                        )
                    else:
                        last_changed = midnight

                    last_changed = last_changed.astimezone(TZ_UTC)
                else:
                    last_changed = None

                # Set the data.
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
                    raise ScrapingError("Cannot parse diner status.")

                # Append to results.
                statuses.append(Status(value=value, last_changed=last_changed))

            # Append to results.
            results.append(
                StatusRow(
                    timestamp=timestamp,
                    deadline=timestamp if has_deadline else None,
                    statuses=statuses,
                )
            )

        return results

    def _get_soup(self, content: bytes) -> BeautifulSoup:
        return BeautifulSoup(content, "html.parser")

    def _from_cache(self, key: str) -> Optional[tuple[bytes, datetime]]:
        try:
            response, valid_until = self.cache[key]
        except KeyError:
            return None

        return response if now() < valid_until else None

    def _login(self) -> None:
        # Verify username and password.
        if self.username is None and self.password is None:
            raise LoginError("Cannot login without username and password.")

        # Create request
        payload = {"login": self.username, "pass": self.password}
        response = requests.get(BASE_URL + "login.php", params=payload)

        # Check for errors.
        if response.status_code != 200:
            raise SessionError("Unexpected status code: %d" % response.status_code)

        if "r=failed" in response.url:
            raise LoginError("Unable to login. Username and/or password incorrect.")

        # Get session parameter.
        query_string = urlparse.urlparse(response.url).query
        query_array = urlparse.parse_qs(query_string)

        try:
            self.session = (
                query_array.get("session_id")[0],
                timeout(seconds=TIMEOUT_SESSION),
            )
        except IndexError:
            raise ScrapingError("Unable to strip session identifier from URL.")

        # Login redirects to main page, so cache it.
        self.cache["main_page"] = (response.content, timeout(seconds=TIMEOUT_CACHE))

    def _get_session(self, is_retry: bool = False, renew: bool = True) -> Optional[str]:
        # Start a session.
        if self.session is None:
            if not renew:
                return

            self._login()

        # Check if session is still valid.
        session, valid_until = self.session

        if valid_until < now():
            if not renew:
                return

            if is_retry:
                raise SessionError("Unable to renew session.")
            else:
                self.session = None
                return self._get_session(is_retry=True)

        return session

    def _main_page(
        self,
        is_retry: bool = False,
        data: Optional[dict[str, Union[str, int]]] = None,
        post: bool = False,
    ) -> BeautifulSoup:
        if data is None:
            data = {}

        # Prepare request.
        if post:
            payload = {
                "day[]": "",
                "messageboard": "",
                "nieuwetijd": "",
                "session_id": self._get_session(),
                "submittype": 2,
                "veranderdag": "",
                "what": -1,
                "who": -1,
            }
            payload.update(data)

            response = requests.post(BASE_URL + "main.php", data=payload)
        else:
            payload = {"session_id": self._get_session()}
            payload.update(data)

            response = self._from_cache("main_page") or requests.get(
                BASE_URL + "main.php", params=payload
            )

        if type(response) != str and type(response) != bytes:
            # Check for errors.
            if response.status_code != 200:
                raise SessionError("Unexpected status code: %d" % response.status_code)

            # Session expired.
            if "login.php" in response.url:
                self.clear_cache()

                # Determine to retry or not.
                if is_retry:
                    raise SessionError("Unable to retrieve page: main.php")
                else:
                    return self._main_page(is_retry=True, data=data, post=post)

            # Convert to string, we do not need the rest anymore.
            response = response.content

        # Update cache and session.
        self.session = (self.session[0], timeout(seconds=TIMEOUT_SESSION))
        self.cache["main_page"] = (response, timeout(seconds=TIMEOUT_CACHE))

        return response
