import logging

from requests.exceptions import HTTPError
from functools import wraps
from flask import request
from flask import current_app as app

from utils import http
from security.dms_client import authorize


logger = logging.getLogger(__name__)


def jwt_auth():
    def _jwt_auth(f):
        @wraps(f)
        def __jwt_auth(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')
            auth_prefix = 'Bearer '

            if auth_header.startswith(auth_prefix):
                try:
                    jwt_token = auth_header[len(auth_prefix):].strip()

                    user = authorize(base_url=app.config['DMS']['ENDPOINT'], jwt_token=jwt_token)

                    if not user:
                        return http.response_error_401()
                    else:
                        return f(*args, **kwargs)

                except HTTPError:
                    logger.exception('Can not authenticate using provided JWT token')
                    return http.response_error_401()
            else:
                return http.response_error_401()

        return __jwt_auth

    return _jwt_auth
