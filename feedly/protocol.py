import time
from typing import Optional, Dict, Union, Any, List
from requests.exceptions import HTTPError
from requests import Response
import json
import datetime


class WrappedHTTPError(HTTPError):
    def __init__(self, ex:HTTPError):
        super().__init__(request=ex.request, response=ex.response)
        self.id = None
        self.message = None
        try:
            info = json.loads(ex.response.text)
            self.id = info.get('errorId')
            self.message = info.get('errorMessage')
        except:
            pass

    @property
    def reason(self):
        if self.message:
            return f'{self.response.reason}: {self.message}'
        else:
            return self.response.reason


class UnauthorizedAPIError(WrappedHTTPError):
    pass


class BadRequestAPIError(WrappedHTTPError):
    pass


class ServerAPIError(WrappedHTTPError):
    pass


class RateLimitedAPIError(WrappedHTTPError):
    def __init__(self, ex:HTTPError=None):
        """
        This error can occur when receiving a rate limited response (429) OR an attempt to use a rate limited client
        :param ex: the underlying error if the first case
        """
        if ex:
            super().__init__(ex)
        else:
            self.message = 'Request Aborted: Client is rate limited'
            self.response = {'status_code': 429, 'headers': {}, 'reason': 'too many requests'}


def _try_int(str) -> Optional[int]:
    try:
        return int(str)
    except ValueError as e:
        return None


class RateLimiter:
    def __init__(self):
        self.count:int = None
        self.limit:int = None
        self.until:float = None

    @property
    def rate_limited(self):
        if self.count and self.limit and self.until:
            return self.count >= self.limit and time.time() < self.until

    def make_rate_limited(self, t=60):
        self.count = 1
        self.limit = 1
        self.until = time.time()+t

    def update(self, response:Response):
        headers = [response.headers.get(h) for h in ['X-RateLimit-Count', 'X-RateLimit-Limit', 'X-RateLimit-Reset']]
        headers = [_try_int(h) if h is not None else None for h in headers]
        count,limit,reset = headers
        if count:
            self.count = count
        if limit:
            self.limit = limit
        if reset:
            self.until = time.time() + reset

        if count and limit:
            return count <= limit

    def __repr__(self):
        if self.count and self.limit and self.until:
            return f'<RateLimiter count={self.count} limit={self.limit} until={datetime.datetime.fromtimestamp(self.until).isoformat()}>'

        return '<RateLimiter>'

    def __str__(self):
        return self.__repr__()

class APIClient:

    def __init__(self):
        self.rate_limiter:RateLimiter = RateLimiter()

    def do_api_request(self, relative_url:str, method:str=None, data:Dict=None,
                       timeout: int = None, max_tries: int = None) -> Union[Dict[str, Any], List[Any]]:
        raise ValueError
