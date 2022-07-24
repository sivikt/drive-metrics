import logging

from .intents import Intent
from utils.formatting import ignore_if_empty
from db_sparql_api.db_sparql_api import DBSparqlApi, DBSparqlApiException
from db_sparql_api.prefixes import declare_prefixes, OWL, XSD, TRIPQA


class DefaultLogger:
    def __init__(self):
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

    def log(self, intent: Intent):
        self.logger.info('User asked %s', intent)


class IntentsLogger(DefaultLogger):
    def __init__(self, data_graph_name: str, db_api: DBSparqlApi):
        super().__init__()

        self.db_api = db_api
        self.data_graph_name = data_graph_name

    def log(self, intent: Intent):
        super().log(intent=intent)

        if intent and intent.get_natural_language_question():
            nl_question = intent.get_natural_language_question()

            query = (
                f"{declare_prefixes(OWL, XSD, TRIPQA)} "
                 "INSERT DATA { "
                    f"{ignore_if_empty('GRAPH <{}> {{', self.data_graph_name)} "
                        f"{TRIPQA.abbr}:{intent.get_uuid()} a {TRIPQA.abbr}:Question, {OWL.abbr}:NamedIndividual ; "
                                    f"{TRIPQA.abbr}:hasIntentId \"{intent.__class__.__name__}\"^^{XSD.abbr}:string ; "
                                    f"{TRIPQA.abbr}:englishLanguage \"{nl_question}\"^^{XSD.abbr}:string . "
                    f"{ignore_if_empty('}}', self.data_graph_name)} "
                 "}"
            )

            try:
                self.db_api.update(query)
            except DBSparqlApiException:
                self.logger.exception('Error while inserting new question into knowledge base')

    def ignore_if_empty(self, template: str, param):
        return template.format(param) if param else ""
