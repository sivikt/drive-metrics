import logging
import json
import time

from logging import Logger
from typing import Callable, Tuple, Type, Union
from functools import wraps
from flask import Response


logger = logging.getLogger(__name__)


def create_api_error(error_code: str = 'unknown', error_desc: str = 'unknown'):
    return {
        'error_code': error_code,
        'error_desc': error_desc
    }


def response_error_404(error_code: str, error_desc: str) -> Response:
    return Response(json.dumps(create_api_error(error_code, error_desc)), status=404, mimetype='application/json')


def response_error_400(error_code: str, error_desc: str) -> Response:
    return Response(json.dumps(create_api_error(error_code, error_desc)), status=400, mimetype='application/json')


def response_error_401() -> Response:
    return Response(json.dumps(create_api_error('unauthorized', 'bad credentials')), status=401, mimetype='application/json')


def response_error_500(error_code: str, error_desc: str) -> Response:
    return Response(json.dumps(create_api_error(error_code, error_desc)), status=500, mimetype='application/json')


def response_200(data) -> Response:
    return Response(json.dumps(data), status=200, mimetype='application/json')


def retry(exception: Union[Type[Exception], Tuple[Type[Exception]]],
          num_tries: int = 3,
          delay: float = 1,
          log: Logger = None) -> Callable:

    if num_tries < 1:
        raise ValueError('The number of tries should be at least 1')

    def retry_decorator(f: Callable) -> Callable:
        @wraps(f)
        def f_with_retries(*args, **kwargs):
            nonlocal delay, num_tries

            while num_tries > 0:
                try:
                    return f(*args, **kwargs)
                except exception as e:
                    msg = f'{e}.\nRetrying {f.__name__}(*{args},**{kwargs}) in {delay} seconds'
                    if log:
                        log.error(msg)
                    else:
                        logger.exception(f'Failed to retry {f.__name__}(*{args},**{kwargs}) {num_tries} times')
                        raise e

                time.sleep(delay)
                num_tries -= 1
                delay *= 1.2

        return f_with_retries

    return retry_decorator
