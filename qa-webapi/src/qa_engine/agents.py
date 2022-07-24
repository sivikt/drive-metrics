import logging

from .nlu import IntentionEstimator
from .intents import UnknownIntent
from .answers import KnownAnswer, NotUnderstandAnswer, CanNotAnswer
from .intents_logging import IntentsLogger, DefaultLogger
from db_sparql_api.db_sparql_api import DBSparqlApi, DBSparqlApiException
from utils.timer import create_elapsed_timer_str


class SparqlAgent:
    def __init__(self,
                 data_graph_name: str,
                 db_api: DBSparqlApi,
                 intents_estimator: IntentionEstimator,
                 intents_logger: IntentsLogger):
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

        self.db_api = db_api
        self.intents_estimator = intents_estimator
        self.data_graph_name = data_graph_name
        self.intents_logger = intents_logger if intents_logger else DefaultLogger()

    def ask(self, question: str):
        intent = self.intents_estimator.estimate(question)

        try:
            if type(intent) != UnknownIntent:
                sw = create_elapsed_timer_str('sec')
                query = intent.as_sparql(graph_name=self.data_graph_name)
                response = self.db_api.query(sparql=query)
                self.logger.debug('Got answer from GraphDB API in [%s]', sw())

                answer = KnownAnswer(intent=intent, answer=response['result'], answer_format=response['format'])
            else:
                answer = NotUnderstandAnswer(intent=intent)
        except DBSparqlApiException:
            self.logger.exception('Error while querying knowledge base for intent %s', intent)
            answer = CanNotAnswer(intent=intent)

        try:
            self.intents_logger.log(intent=intent)
        except Exception:
            self.logger.exception('Error while logging processed intent %s', intent)

        return answer
