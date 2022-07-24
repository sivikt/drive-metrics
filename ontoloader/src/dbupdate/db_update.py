import requests

from dbapi.graphdb_api import GraphDBApi, GraphDBApiException, GraphDBUpdateException
from dbapi.prefixes import declare_prefixes, OWL, XSD


class DbUpdater(GraphDBApi):
    def __init__(self,
                 **kwargs):

        super().__init__(**kwargs)

        self.repo_ops_endpoint = self.graphdb_endpoint + f'/rest/repositories'

    def fresh_update(self, repo_config_path: str, statements_path: str, version: str):
        if self.is_old_repo_version():
            self.logger.info('Starting fresh DB update using repository config %s', repo_config_path)

            self.delete_repo()
            self.create_repo(repo_config_path=repo_config_path, version=version)
            self.create_ontology(statements_path=statements_path)

            self.logger.info('Finished fresh DB update using repository config %s', repo_config_path)
        else:
            self.logger.info('Repository %s of version %s is up-to-date', self.repository_id, version)

    def is_old_repo_version(self):
        pass

    def create_ontology(self, statements_path: str):
        pass

    def create_repo(self, repo_config_path: str, version: str):
        self.logger.info('Creating repository %s', repo_config_path)

        try:
            response = self._do_authorized_call(
                func=requests.post,
                url=self.repo_ops_endpoint,
                files=dict(config=open(repo_config_path, 'rb'))
            )

            if response.status_code < 400:
                self.logger.info('Created repository from %s', repo_config_path)
            else:
                self.logger.error(
                    'Failed to create repository from %s, got response [%s] from [%s]',
                    repo_config_path, response.text, response.url
                )
                raise GraphDBUpdateException(response.text)
        except GraphDBApiException:
            self.logger.exception('Error while creating repository from %s', repo_config_path)

    def delete_repo(self):
        self.logger.info('Deleting repository %s', self.repository_id)

        try:
            response = self._do_authorized_call(
                func=requests.delete,
                url=self.query_endpoint
            )

            if response.status_code >= 400 and response.status_code != 404:
                self.logger.error('Failed to delete existing repository, got response [%s] from [%s]', response.text, response.url)
                raise GraphDBUpdateException(response.text)
            else:
                self.logger.info('Deleted repository %s', self.repository_id)

        except GraphDBApiException:
            self.logger.exception('Error while deleting repository %s', self.repository_id)
