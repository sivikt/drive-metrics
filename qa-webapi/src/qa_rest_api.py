import logging
import re

from flask import Blueprint
from flask import current_app as app
from flask_restful import reqparse

from qa_engine.agents import SparqlAgent
from qa_engine.intents_logging import IntentsLogger
from qa_engine.nlu import IntentionEstimator
from db_sparql_api.db_sparql_api import DBSparqlApi
from db_sparql_api.prefixes import declare_prefixes, OWL, RDF, TRIP
from utils import http
from utils.formatting import ignore_if_empty

from config.config import CONFIGURATION

import auth


mod = Blueprint('qa_rest_api', __name__)


logger = logging.getLogger(__name__)


DB_API = DBSparqlApi(
    graphdb_endpoint=CONFIGURATION['GRAPHDB']['ENDPOINT'],
    repository_id=CONFIGURATION['GRAPHDB']['REPOSITORY_ID'],
    username=CONFIGURATION['GRAPHDB']['USERNAME'],
    password=CONFIGURATION['GRAPHDB']['PASSWORD']
)

INTENTS_LOGGER = IntentsLogger(
    data_graph_name=CONFIGURATION['GRAPHDB']['QA_STATS_DATA_GRAPH'],
    db_api=DB_API
)

INTENTION_ESTIMATOR = IntentionEstimator(
    project_id=CONFIGURATION['DIALOGFLOW']['PROJECT_ID']
)


SPARQL_AGENT = SparqlAgent(
    data_graph_name=CONFIGURATION['GRAPHDB']['MAIN_TRIPS_DATA_GRAPH'],
    db_api=DB_API,
    intents_estimator=INTENTION_ESTIMATOR,
    intents_logger=INTENTS_LOGGER
)


@mod.route('/ask', methods=['GET'])
@auth.jwt_auth()
def ask_question():
    parser = reqparse.RequestParser()
    parser.add_argument('question', help='Question is required', required=True)
    args = parser.parse_args()

    answer = SPARQL_AGENT.ask(args['question'])

    return http.response_200(answer.get_details())


def is_valid_fragment_id(value):
    return True if re.match("^[a-zA-Z0-9_\-]*$", value) else False


@mod.route('/resource/named/<fragment_identifier>', methods=['GET'])
@auth.jwt_auth()
def get_named_resource_details(fragment_identifier):
    graph_name = app.config['GRAPHDB']['MAIN_TRIPS_DATA_GRAPH']

    if not is_valid_fragment_id(fragment_identifier):
        return http.response_error_400(
            'Fragment identifiers can not contain any special characters',
            'invalid_fragment_identifier'
        )

    query = (
       f"{declare_prefixes(OWL, RDF, TRIP)} "
       f"CONSTRUCT {{ {TRIP.abbr}:{fragment_identifier} ?prop ?value . }}"
        "WHERE { "
            f"{ignore_if_empty('GRAPH <{}> {{', graph_name)} "
                f"{TRIP.abbr}:{fragment_identifier} ?prop ?value . "
                "FILTER ( "
                    "!isBlank(?prop) && "
                   f"(?prop != {OWL.abbr}:topDataProperty) && "
                   f"(?prop != {OWL.abbr}:topObjectProperty) && "
                   f"!((?prop = {RDF.abbr}:type) && isBlank(?value)) "
                ") "
            f"{ignore_if_empty('}}', graph_name)} "
        "}"
    )

    return http.response_200(DB_API.query(query))


@mod.route('/resources/named/', methods=['GET'])
@auth.jwt_auth()
def get_named_resources_details():
    parser = reqparse.RequestParser()
    parser.add_argument(
        'as',
        dest='fragment_identifiers',
        action='append',
        help='List of fragment identifiers',
        location='args',
        required=True
    )
    args = parser.parse_args()
    fragment_identifiers = args.get('fragment_identifiers', [])

    for frag_id in fragment_identifiers:
        if not is_valid_fragment_id(frag_id):
            return http.response_error_400(
                'Fragment identifiers can not contain any special characters',
                'invalid_fragment_identifier'
            )

    def construct():
        definitions = ''
        for i, fr_id in enumerate(fragment_identifiers):
            definitions += f"{TRIP.abbr}:{fr_id} ?prop{i} ?value{i} ."

        return definitions

    def where():
        definitions = ''

        for i, fr_id in enumerate(fragment_identifiers):
            definitions += (
                f"{TRIP.abbr}:{fr_id} ?prop{i} ?value{i} . "
                "FILTER ("
                   f"!isBlank(?prop{i}) && "
                   f"(?prop{i} != {OWL.abbr}:topDataProperty) && "
                   f"(?prop{i} != {OWL.abbr}:topObjectProperty) && "
                   f"!((?prop{i} = {RDF.abbr}:type) && isBlank(?value{i})) "
                ")"
            )

        return definitions

    graph_name = app.config['GRAPHDB']['MAIN_TRIPS_DATA_GRAPH']

    query = (
       f"{declare_prefixes(OWL, RDF, TRIP)} "
       f"CONSTRUCT {{ {construct()} }}"
        "WHERE { "
            f"{ignore_if_empty('GRAPH <{}> {{', graph_name)} "
                f"{where()}"
            f"{ignore_if_empty('}}', graph_name)} "
        "}"
    )

    return http.response_200(DB_API.query(query))


@mod.route('/resources/named/trip', methods=['GET'])
@auth.jwt_auth()
def get_trip_l1label_details():
    parser = reqparse.RequestParser()
    parser.add_argument(
        'trip_id',
        dest='trip_id',
        help='Trip identifier',
        location='args',
        required=True
    )
    args = parser.parse_args()
    trip_id = args.get('trip_id', [])

    graph_name = app.config['GRAPHDB']['MAIN_TRIPS_DATA_GRAPH']

    query = (
       f'{declare_prefixes(OWL, RDF, TRIP)} '
       'CONSTRUCT { '
           f'?l1label a {TRIP.abbr}:L1Label;'
                   f'{TRIP.abbr}:ofQuantity ?l1labelQnty . '
       '}'
       'WHERE { '
          'SELECT ?l1label (COUNT(?l1label) AS ?l1labelQnty) '
          'WHERE { ' 
               f"{ignore_if_empty('GRAPH <{}> {{', graph_name)} "
                   f'{TRIP.abbr}:{trip_id} a {TRIP.abbr}:Trip ;'
                                f'{TRIP.abbr}:hasRoute ?route .'
                   f'?route {TRIP.abbr}:hasMotionStep ?ms .'
                   f'?ms a {TRIP.abbr}:MotionStep, {TRIP.abbr}:RoadMatchedMotionStep;'
                       f'{TRIP.abbr}:hasL1Label ?l1label;'
                       f'{TRIP.abbr}:onRoadSegment ?roadseg .'
               f"{ignore_if_empty('}}', graph_name)} "
          '}'
          'GROUP BY ?l1label'
       '}'
    )

    return http.response_200(DB_API.query(query))


@mod.route('/resource/anonym/', methods=['GET'])
@auth.jwt_auth()
def get_anonym_resource_details():
    pass


@mod.route('/ping', methods=['GET'])
def ping():
    return 'pong'


@mod.route('/version', methods=['GET'])
def version():
    return app.config['VERSION']
