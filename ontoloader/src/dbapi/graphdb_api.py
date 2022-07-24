import logging
import requests
from requests import Response
from typing import Callable

#from SPARQLWrapper import RDFXML


class GraphDBApiException(Exception):
    pass


class GraphDBQueryException(GraphDBApiException):
    pass


class GraphDBUpdateException(GraphDBApiException):
    pass


class GraphDBApi:
    def __init__(self, graphdb_endpoint: str, repository_id: str, username: str = None, password: str = None):
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

        self.repository_id = repository_id
        self.graphdb_endpoint = graphdb_endpoint
        self.query_endpoint = graphdb_endpoint + f'/repositories/{repository_id}'
        self.update_endpoint = graphdb_endpoint + f'/repositories/{repository_id}/statements'
        self.login_endpoint = graphdb_endpoint + f"/rest/login/{username if username else 'admin'}"
        self.transaction_endpoint = self.graphdb_endpoint + f'/repositories/{self.repository_id}/transactions'
        self.username = username
        self.password = password
        self.jwt_header = None

        self._authorize()

    def _active_transaction_endpoint(self, transaction_id: str):
        return self.transaction_endpoint + f'/{transaction_id}'
    
    def _authorize(self) -> str:
        if self.username:
            try:
                auth_response = requests.post(self.login_endpoint, headers={'X-GraphDB-Password': self.password}, verify=False)

                if auth_response.status_code < 400:
                    self.jwt_header = {'Authorization': auth_response.headers['Authorization']}
                else:
                    raise GraphDBApiException(f'GraphDB server {self.graphdb_endpoint} failed to authenticate with provided credentials')

                return auth_response.json()
            except Exception:
                self.logger.exception('Errors during authentication')
                raise GraphDBApiException(f'Can not authenticate at {self.graphdb_endpoint}')
        else:
            self.jwt_header = None
            return None

    def _do_authorized_call(self, func: Callable[..., Response], max_retries: int = 1, **kwargs) -> Response:
        if not self.jwt_header:
            return func(**kwargs)
        else:
            if 'headers' in kwargs:
                kwargs['headers'].update(self.jwt_header)
            else:
                kwargs['headers'] = self.jwt_header
            
            try:
                response = func(**kwargs, verify=False)
            except Exception:
                self.logger.exception('Failed to execute function %s', func.__name__)
                raise GraphDBApiException('Failed making authorized request')
            
            if response.status_code == 401:
                if max_retries > 0:
                    self._authorize()
                    return self._do_authorized_call(func=func, max_retries=max_retries-1, **kwargs)
                else:
                    request_info = {k: kwargs[k] for k in kwargs if (not self.jwt_header) or (k not in self.jwt_header)}
                    raise GraphDBApiException(f'Failed making authorized request using parameters {request_info}')
            else:
                return response

    def query(self, sparql: str) -> dict:
        response = self._do_authorized_call(
            func=requests.get,
            url=self.query_endpoint,
            params={'query': sparql}
        )

        if response.status_code < 400:
            content_type_declarations = response.headers['Content-Type'].split(';')

            return {
                'result': response.text,
                'format': content_type_declarations[0] if len(content_type_declarations) > 0 else None
            }
        else:
            self.logger.error('Failed to execute DB query response [%s] from [%s]', response.text, response.url)
            raise GraphDBQueryException(response.text)

    def update(self, sparql: str) -> None:
        response = self._do_authorized_call(func=requests.post, url=self.update_endpoint, params={'update': sparql})

        if response.status_code >= 400:
            self.logger.error('Failed response [%s] from [%s]', response.text, response.url)
            raise GraphDBUpdateException(response.text)

    def update_in_transaction(self, sparql: str) -> None:
        response = self._do_authorized_call(
            func=requests.post,
            url=self.transaction_endpoint
        )

        transaction_id = None
        
        try:          
            if response.status_code == 201:
                location = response.headers['location']
                transaction_id = location[len(self.transaction_endpoint)+1:]
                
                response = self._do_authorized_call(
                    func=requests.put,
                    url=self._active_transaction_endpoint(transaction_id),
                    headers={'Content-Type': 'application/sparql-update'},
                    data=sparql,
                    params={'action': 'UPDATE'}
                )

                if response.status_code >= 400:
                    self.logger.error(
                        'Failed to add statements into transaction %s and commit it. Got response [%s] from [%s]', 
                        transaction_id, response.text, response.url
                    )
                    raise GraphDBUpdateException(response.text)

                response = self._do_authorized_call(
                    func=requests.put,
                    url=self._active_transaction_endpoint(transaction_id),
                    params={'action': 'COMMIT'}
                )

                if response.status_code >= 400:
                    self.logger.error(
                        'Failed to commit transaction %s. Got response [%s] from [%s]',
                        transaction_id, response.text, response.url
                    )
                    raise GraphDBUpdateException(response.text)
            else:
                raise GraphDBUpdateException('Can not start transaction')
        except Exception as err:
            if transaction_id:
                response = self._do_authorized_call(
                    func=requests.delete,
                    url=self._active_transaction_endpoint(transaction_id)
                )
                
                if response.status_code >= 400:
                    self.logger.error(
                        'Failed to rollback transaction %s. Got response [%s] from [%s]', 
                        transaction_id, response.text, response.url
                    )
            
            raise err
