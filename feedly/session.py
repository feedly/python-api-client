import time
from pathlib import Path
from typing import Dict, Any, Union, List, Optional

import logging

import datetime
from urllib.parse import quote_plus

from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError

from requests import Session
import urllib

from feedly.data import FeedlyUser
from feedly.protocol import RateLimitedAPIError, BadRequestAPIError, UnauthorizedAPIError, ServerAPIError, APIClient, WrappedHTTPError
from feedly.stream import EnterpriseStreamId


class FeedlySession(APIClient):
    def __init__(self, auth_token:str, api_host:str='https://feedly.com', name:str='feedly.python.client',
                 user_id:str=None, client_name='feedly.python.client'):
        super().__init__()
        if not client_name:
            raise ValueError('you must identify your client!')

        self.auth_token:str = auth_token
        self.api_host:str = api_host
        self.session = Session()
        self.session.mount('https://feedly.com', HTTPAdapter(max_retries=1)) # as to treat feedly server and connection errors identically
        self.client_name = client_name
        self.timeout:int = 10
        self.max_tries:int = 3
        self.name = urllib.parse.quote_plus(name)

        user_data = {'id': user_id} if user_id else {}
        self._user:FeedlyUser = FeedlyUser(user_data, self)
        self._valid:bool = None

    def __repr__(self):
        return f'<feedly client user={self.user.id}>'

    def __str__(self):
        return self.__repr__()

    def close(self) -> None:
        self._valid = None
        if self.session:
            self.session.close()
            self.session = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def user(self) -> 'FeedlyUser':
        return self._user

    def do_api_request(self, relative_url:str, method:str=None, data:Dict=None,
                       timeout: int = None, max_tries: int = None) -> Union[Dict[str, Any], List[Any]]:
        """
        makes a request to the feedly cloud API (https://developers.feedly.com)
        :param relative_url: the url path and query parts, starting with /v3
        :param data: the post data to send (as json).
        :param method: the http method to use, will default to get or post based on the presence of post data
        :param timeout: the timeout interval
        :param max_tries: the number of tries to do before failing
        :param protocol: the protocol to use (http or https)
        :return: the request result as parsed from json.
        :rtype: dict or list, based on the API response
        :raises: requests.exceptions.HTTPError on failure. An appropriate subclass may be raised when appropriate,
         (see the ones defined in this module).
        """

        if self.timeout is None:
            timeout = self.timeout

        if max_tries is None:
            max_tries = self.max_tries

        if self.auth_token is None:
            raise ValueError('authorization token required!')

        if relative_url[0] != '/':
            relative_url = '/' + relative_url

        if not relative_url.startswith('/v3/'):
            raise ValueError(f'invalid endpoint {relative_url} -- must start with /v3/ See https://developers.feedly.com')

        if 10 < max_tries < 0:
            raise ValueError('invalid max tries')

        full_url = f'{self.api_host}{relative_url}'
        if '?client=' not in full_url and '&client=' not in full_url:
            full_url += ('&' if '?' in full_url else '?') + 'client=' + quote_plus(self.client_name)

        tries = 0
        if method is None:
            method = 'get' if data is None else 'post'

        if method == 'get' and data is not None:
            raise ValueError('post data not allowed for GET requests')

        try:
            if self.rate_limiter.rate_limited:
                raise RateLimitedAPIError(None)
            while True:
                tries += 1
                if self.rate_limiter.rate_limited:
                    until = datetime.datetime.fromtimestamp(self.rate_limiter.until).isoformat()
                    raise ValueError(f'Too many requests. Client is rate limited until {until}')
                headers = {'Authorization': self.auth_token}
                if data:
                    headers['Content-Type'] = 'application/json'

                resp = None
                conn_error = None
                try:
                    resp = self.session.request(method, full_url, headers=headers, timeout=timeout, json=data, verify=False)
                except OSError as e:
                    conn_error = e

                if resp:
                    self.rate_limiter.update(resp)

                if not conn_error and resp.ok:
                    return resp.json() if resp.content is not None and len(resp.content) > 0 else None
                else:
                    if tries == max_tries or (resp is not None and 400 <= resp.status_code <= 500): # don't retry bad requests:
                        if conn_error:
                            raise conn_error
                        else:
                            resp.raise_for_status()
                    logging.warning('Error for %s: %s', relative_url, conn_error if conn_error else resp.text)
                    time.sleep(2 ** (tries - 1))  # 1 second, then 2, 4, 8, etc.
        except HTTPError as e:
            code = e.response.status_code
            if code == 400:
                raise BadRequestAPIError(e)
            elif code == 401:
                raise UnauthorizedAPIError(e)
            elif code == 429:
                if not self.rate_limiter.rate_limited:
                    self.rate_limiter.make_rate_limited()
                raise RateLimitedAPIError(e)
            elif code == 500:
                raise ServerAPIError(e)

            raise e

if __name__ == '__main__':
        logging.basicConfig(level='DEBUG')
        token = (Path.home() / 'access.token').read_text().strip()
        # print(sess.user['fullName'])

        uid = 'uid'
        sess = FeedlySession(auth_token=token, user_id=uid)

        # sess.user.get_enterprise_tags()
        # sess.user.get_enterprise_categories()

        # with FeedlySession(auth_token=token, user_id=uid) as sess:
        #     opts = StreamOptions(max_count=30)
        #     for i, eid in enumerate(sess.user.get_category('politics').stream_ids(opts)):
        #         print(i, eid)