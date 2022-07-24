import logging
import uuid
import dialogflow_v2 as dialogflow

from google.protobuf.json_format import MessageToDict

from .intents import (
    Intent,
    UnknownIntent,
    ListTripsIntent,
    TripRouteIntent,
    TripsOnDateIntent,
    DescribeTripIntent,
    ListDriverTripsIntent,
    DriverTripsOnDateIntent,
    TripsWithEventOnDateIntent,
    TripEventLocationIntent,
    TripLocationsIntent
)

from utils.timer import create_elapsed_timer_str


INTENTS_MAPPING = {
    'unknown': None,
    'describe_TRIP': DescribeTripIntent,
    'what_TRIP_route': TripRouteIntent,
    'list_trips': ListTripsIntent,
    'what_trips_on_DATE': TripsOnDateIntent,
    'list_DRIVER_trips': ListDriverTripsIntent,
    'what_DRIVER_trips_on_DATE': DriverTripsOnDateIntent,
    'what_trips_have_EVENT_on_DATE': TripsWithEventOnDateIntent,
    'at_what_LOCATION_TRIP_has_EVENT': TripEventLocationIntent,
    'which_LOCATIONS_covered_by_TRIP': TripLocationsIntent
}


class IntentionEstimator:
    def __init__(self, project_id: str):
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

        self.project_id = project_id
        self.session_id = str(uuid.uuid4())

        self.session_client = dialogflow.SessionsClient()
        self.session = self.session_client.session_path(project_id, self.session_id)

        self.logger.info('created DialogFlow Session %s', self.session)

    def __ask_dialogflow(self, question: str):
        sw = create_elapsed_timer_str('sec')

        text_input = dialogflow.types.TextInput(text=question, language_code='en')
        query_input = dialogflow.types.QueryInput(text=text_input)

        response = self.session_client.detect_intent(session=self.session, query_input=query_input)

        self.logger.debug('Got answer from Dialogflow in [%s]', sw())

        return MessageToDict(response.query_result)

    def estimate(self, question: str) -> Intent:
        intent = UnknownIntent(nl_question=question)

        dlg_result = self.__ask_dialogflow(question)

        self.logger.debug('Dialogflow returned result [%s]', dlg_result)

        if 'intent' in dlg_result:
            intent_name = dlg_result['intent']['displayName']

            if (intent_name in INTENTS_MAPPING) and (INTENTS_MAPPING[intent_name] is not None):
                intent = INTENTS_MAPPING[intent_name](
                    nl_question=question,
                    confidence=dlg_result['intentDetectionConfidence'],
                    params_values=dlg_result['parameters']
                )

        if (type(intent) != UnknownIntent) and (intent.has_missed_params()):
            self.logger.debug('Got incorrectly formulated intent %s which is missing required parameters ', intent)
            intent = UnknownIntent(nl_question=question, probable_intent=intent)

        return intent
