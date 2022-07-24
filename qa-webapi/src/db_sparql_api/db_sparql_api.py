import logging
import requests
from requests import Response
from typing import Callable, Optional

#from SPARQLWrapper import RDFXML


class DBSparqlApiException(Exception):
    pass


class DBSparqlQueryException(DBSparqlApiException):
    pass


class DBSparqlUpdateException(DBSparqlApiException):
    pass


class DBSparqlApi:
    def __init__(self, graphdb_endpoint: str, repository_id: str, username: str = None, password: str = None):
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

        self.graphdb_endpoint = graphdb_endpoint
        self.query_endpoint = graphdb_endpoint + f'/repositories/{repository_id}'
        self.update_endpoint = graphdb_endpoint + f'/repositories/{repository_id}/statements'
        self.login_endpoint = graphdb_endpoint + f"/rest/login/{username if username else 'admin'}"
        self.username = username
        self.password = password
        self.jwt_header = None

        self.__authorize()

    def __authorize(self) -> str:
        if self.username:
            auth_response = requests.post(self.login_endpoint, headers={'X-GraphDB-Password': self.password}, verify=False)

            if auth_response.status_code < 400:
                self.jwt_header = {'Authorization': auth_response.headers['Authorization']}
            else:
                raise DBSparqlApiException(f'Can not authenticate at {self.graphdb_endpoint}')

            return auth_response.json()
        else:
            self.jwt_header = None
            return None

    def __do_authorized_call(self, func: Callable[..., Response], max_retries: int = 1, **kwargs) -> Response:
        if not self.jwt_header:
            return func(**kwargs)
        else:
            if 'headers' in kwargs:
                kwargs['headers'].update(self.jwt_header)
            else:
                kwargs['headers'] = self.jwt_header

            response = func(**kwargs, verify=False)

            if response.status_code == 401:
                if max_retries > 0:
                    self.__authorize()
                    return self.__do_authorized_call(func=func, max_retries=max_retries-1, **kwargs)
                else:
                    request_info = {k: kwargs[k] for k in kwargs if (not self.jwt_header) or (k not in self.jwt_header)}
                    raise DBSparqlApiException(f'Failed making authorized request using parameters {request_info}')
            else:
                return response

    def query(self, sparql: str) -> dict:
        response = self.__do_authorized_call(
            func=requests.get,
            url=self.query_endpoint,
            params={'query': sparql},
            headers={'Accept': 'text/n3'}
        )

        if response.status_code < 400:
            content_type_declarations = response.headers['Content-Type'].split(';')

            return {
                'result': response.text,
                'format': content_type_declarations[0] if len(content_type_declarations) > 0 else None
            }
        else:
            self.logger.error('Failed response [%s] from [%s]', response.text, response.url)
            raise DBSparqlQueryException(response.text)

    def update(self, sparql: str) -> None:
        response = self.__do_authorized_call(func=requests.post, url=self.update_endpoint, params={'update': sparql})

        if response.status_code >= 400:
            self.logger.error('Failed response [%s] from [%s]', response.text, response.url)
            raise DBSparqlUpdateException(response.text)
