import time
from pathlib import Path
from typing import Dict, Any, Union, List, Optional

import logging

import datetime
from urllib.parse import quote_plus

from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError

from requests import Session

from feedly.data import FeedlyUser
from feedly.protocol import RateLimitedAPIError, BadRequestAPIError, UnauthorizedAPIError, ServerAPIError, APIClient, WrappedHTTPError


class Auth:
    """
    simple class to manage tokens
    """
    def __init__(self, client_id:str='feedlydev', client_secret:str='feedlydev'):
        self.client_id:str = client_id
        self.client_secret:str = client_secret
        self._auth_token:str = None
        self.refresh_token:str = None

    @property
    def auth_token(self):
        return self._auth_token

    @auth_token.setter
    def auth_token(self, token:str):
        self._auth_token = token


class FileAuthStore(Auth):
    """
    a file based token storage scheme
    """
    def __init__(self, token_dir:Path, client_id:str='feedlydev', client_secret:str='feedlydev'):
        """

        :param token_dir: the directory to store the tokens
        :param client_id: the client id to use when refreshing the auth token. the default value works for developer tokens.
        :param client_secret: the client secret to use when refreshing the auth token. the default value works for developer tokens.
        """
        super().__init__(client_id, client_secret)
        if not token_dir.is_dir():
            raise ValueError(f'{token_dir.absolute()} does not exist!')

        refresh_path = token_dir / 'refresh.token'
        if refresh_path.is_file():
            self.refresh_token = refresh_path.read_text().strip()

        self.auth_token_path:Path = token_dir / 'access.token'
        self._auth_token = self.auth_token_path.read_text().strip()

    @Auth.auth_token.setter
    def auth_token(self, token:str):
        self._auth_token = token
        self.auth_token_path.write_text(token)


class FeedlySession(APIClient):
    def __init__(self, auth:Union[str, Auth], api_host:str='https://feedly.com', user_id:str=None, client_name='feedly.python.client'):
        """
        :param auth: either the access token str to use when making requests or an Auth object to manage tokens
        :param api_host: the feedly api server host.
        :param user_id: the user id to use when making requests. If not set, a request will be made to determine the user from the auth token.
        :param client_name: the name of your client, set this to something that can identify your app.
        """
        super().__init__()
        if not client_name:
            raise ValueError('you must identify your client!')

        if isinstance(auth, str):
            token:str = auth
            auth = Auth()
            auth.auth_token = token

        self.auth:Auth = auth
        self.api_host:str = api_host
        self.session = Session()
        self.session.mount('https://feedly.com', HTTPAdapter(max_retries=1)) # as to treat feedly server and connection errors identically
        self.client_name = client_name
        self.timeout:int = 10
        self.max_tries:int = 3

        user_data = {'id': user_id} if user_id else {}
        self._user:FeedlyUser = FeedlyUser(user_data, self)
        self._valid:bool = None
        self._last_token_refresh_attempt:float = 0

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

        if self.auth.auth_token is None:
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
                headers = {'Authorization': self.auth.auth_token}
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
                if not relative_url.startswith('/v3/auth') and self.auth.refresh_token and time.time() - self._last_token_refresh_attempt > 86400:
                    try:
                        self._last_token_refresh_attempt = time.time()
                        auth_data = {'refresh_token': self.auth.refresh_token, 'grant_type': 'refresh_token',
                                     'client_id': self.auth.client_id, 'client_secret': self.auth.client_secret}
                        token_data = self.do_api_request('/v3/auth/token', data=auth_data)
                        self.auth.auth_token = token_data['access_token']
                        return self.do_api_request(relative_url=relative_url, method=method, data=data, timeout=timeout, max_tries=max_tries)
                    except Exception as e2:
                        logging.info('error refreshing access token', exc_info=e2)
                        # fall through to raise auth error
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
        # token = (Path.home() / 'access.token').read_text().strip()
        auth = FileAuthStore(Path.home())
        # print(sess.user['fullName'])

        sess = FeedlySession(auth)

        sess.user.get_enterprise_tags()
        # sess.user.get_enterprise_categories()

        # with FeedlySession(auth_token=token, user_id=uid) as sess:
        #     opts = StreamOptions(max_count=30)
        #     for i, eid in enumerate(sess.user.get_category('politics').stream_ids(opts)):
        #         print(i, eid)