import logging
import uuid
from typing import List, Dict, Callable, Optional, Any
import pathlib
import os

from nameparser import HumanName

from utils.formatting import ignore_if_empty
from utils.date import to_utc_iso_format_day_interval
from db_sparql_api.prefixes import (
    declare_prefixes,
    TRIP,
    TRIPUI,
    XSD,
    TIME,
    GEOSPARQL,
    RDFS
)

import nltk
_basedir = os.path.abspath(os.path.dirname(__file__))
nltk.data.path.append(str(pathlib.Path(_basedir).parent / 'nltk_data'))
from nltk.tokenize import word_tokenize


class HumanNameNormalized(HumanName):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.first = word_tokenize(self.first)[0].lower() if self.first else self.first
        self.last = word_tokenize(self.last)[0].lower() if self.last else self.last


class IntentParam:
    def __init__(self,
                 param_id: str,
                 meaning: str,
                 required: bool = True,
                 value: Any = None,
                 orig_value: Optional[str] = None,
                 alternative: Any = None, # IntentParam
                 converter: Optional[Callable] = None,
                 **kwargs):

        self.required = required
        self._alternative = alternative
        self._id = param_id
        self._value = value
        self._orig_value = orig_value
        self._meaning = meaning
        self._converter = converter

    @property
    def id(self) -> str:
        return self._id

    @property
    def converter(self) -> Optional[Callable]:
        return self._converter

    @property
    def is_empty(self) -> bool:
        return not self._value

    @property
    def alternative(self): # -> Optional[IntentParam]:
        return self._alternative

    @property
    def value(self) -> Any:
        return self._value

    @property
    def orig_value(self) -> Optional[str]:
        return self._orig_value

    @property
    def meaning(self) -> str:
        return self._meaning

    @property
    def is_required(self) -> bool:
        return self.required

    def is_missed(self):
        def is_missed_alternative(alt_param):
            return (not alt_param) or (alt_param.is_empty and is_missed_alternative(alt_param.alternative))

        if self.is_empty and self.is_required:
            return is_missed_alternative(self.alternative)
        else:
            return False

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return (f"{self.__class__.__name__}("
                f"required='{self.required}, "
                f"param_id={self._id}, "
                f"param_meaning={self._meaning}, "
                f"value={self._value}), "
                f"orig_value={self._orig_value})")


class Intent:
    def __init__(self,
                 nl_question: str,
                 params_definitions: Optional[List[IntentParam]] = None,
                 params_values: Optional[Dict[str, Any]] = None,
                 confidence: float = 1.0):
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

        self.uuid = str(uuid.uuid1())
        self.nl_question = nl_question
        self.confidence = confidence

        self.orig_params_definitions = params_definitions if params_definitions else []
        self.orig_params_values = params_values if params_values else {}

        self.logger.debug(
            'Init intent parameters base on params_def=%s and params_values=%s',
            self.orig_params_definitions,
            self.orig_params_values
        )

        self.params, self.params_index = self.__init_params()

        self.missed_params = [p for p in self.params if p.is_missed()]

    def __str__(self):
        return (f"{self.__class__.__name__}("
                f"uuid='{self.uuid}, "
                f"nl_question='{self.nl_question}, "
                f"params={self.get_params()}, "
                f"confidence={self.confidence})")

    def __init_params(self):
        params = []
        params_index = {}

        def init_param(param_def_, param_values_):
            if not param_def_:
                return None
            elif param_def_.id in params_index:
                return params_index[param_def_.id]
            else:
                alt_param = init_param(param_def_.alternative, param_values_)
                value = param_values_.get(param_def_.id)
                param = self.__create_param(param_def=param_def_, orig_value=value, alternative=alt_param)

                if param.id not in params_index:
                    params.append(param)
                    params_index[param.id] = param

                if alt_param and alt_param.id not in params_index:
                    params.append(alt_param)
                    params_index[alt_param.id] = alt_param

                return param

        for param_def in self.orig_params_definitions:
            init_param(param_def, self.orig_params_values)

        return params, params_index

    def __create_param(self, param_def: IntentParam, orig_value=None, alternative: IntentParam = None):
        value = orig_value

        if orig_value:
            if param_def.converter is not None:
                try:
                    value = param_def.converter(orig_value)
                    self.logger.debug("Convert %s='%s' into '%s'", param_def.id, orig_value, value)
                except Exception:
                    value = None
                    self.logger.exception('Can not apply parameter value map function for parameter "%s"', param_def.id)
        else:
            value = None

        return IntentParam(
            param_id=param_def.id,
            required=param_def.is_required,
            meaning=param_def.meaning,
            alternative=alternative,
            value=value,
            orig_value=orig_value
        )

    def as_sparql(self, graph_name: Optional[str] = None) -> Optional[str]:
        return None

    def get_natural_language_question(self):
        return self.nl_question

    def nl_description(self) -> Optional[str]:
        return None

    def get_params(self) -> List[IntentParam]:
        return self.params

    def get_missed_params(self) -> List[IntentParam]:
        return self.missed_params

    def has_missed_params(self) -> bool:
        return len(self.get_missed_params()) > 0

    def get_param(self, param_id: str):
        if param_id in self.params_index:
            return self.params_index[param_id]
        else:
            self.logger.warning('someone asks for an unknown parameter {}', param_id)
            raise Exception('Unknown parameter', param_id)

    def get_uuid(self):
        return self.uuid

    @staticmethod
    def sparql_and(expr1: str = None, expr2: str = None):
        return f"({expr1}) && ({expr2})" if expr1 and expr2 else (expr1 if expr1 else expr2)


class UnknownIntent(Intent):
    def __init__(self, probable_intent: Optional[Intent] = None, **kwarg):
        super().__init__(**kwarg, confidence=0)
        self.probable_intent = probable_intent

    def get_probable_intent(self) -> Intent:
        return self.probable_intent


class ListTripsIntent(Intent):
    def nl_description(self):
        return 'question is about listing all known trips'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def as_sparql(self, graph_name: Optional[str] = None) -> Optional[str]:
        return (
            f"{declare_prefixes(TRIP, TRIPUI)} "
            "CONSTRUCT { "
                f"{TRIPUI.abbr}:TripsSummaryList a {TRIPUI.abbr}:View ;"
                    f"{TRIPUI.abbr}:containsTrip ?trip . "
            "} "
            "WHERE { "
               f"{ignore_if_empty('GRAPH <{}> {{', graph_name)} "
                    f"?trip a {TRIP.abbr}:Trip . "
                    "FILTER (!isBlank(?trip)) "
               f"{ignore_if_empty('}}', graph_name)} "
            "}"
        )


class TripsOnDateIntent(Intent):
    def nl_description(self):
        return 'question is about listing all known trips started at a specified date'

    def __init__(self, **kwargs):
        kwargs['params_definitions'] = [
            IntentParam(
                param_id='date',
                meaning='trip date',
                converter=lambda x: to_utc_iso_format_day_interval(x) if x else None
            )
        ]

        super().__init__(**kwargs)

    def as_sparql(self, graph_name: Optional[str] = None) -> Optional[str]:
        interval = self.get_param('date').value
        start = interval['start']
        end = interval['end']

        date_in_interval_expr = self.sparql_and(
            f"?ts >= \"{start}\"^^{XSD.abbr}:dateTime",
            f"?ts <= \"{end}\"^^{XSD.abbr}:dateTime"
        )

        return (
            f"{declare_prefixes(TRIP, TRIPUI, XSD, TIME)} "
            "CONSTRUCT { "
                f"{TRIPUI.abbr}:TripsSummaryList a {TRIPUI.abbr}:View ;"
                    f"{TRIPUI.abbr}:containsTrip ?trip . "
            "} "
            "WHERE { "
               f"{ignore_if_empty('GRAPH <{}> {{', graph_name)} "
                   f"?trip a {TRIP.abbr}:Trip ; "
                         f"{TIME.abbr}:hasBeginning ?beg . "
                   f"?beg {TRIP.abbr}:hasTimestamp ?ts . "
                   f"FILTER ( !isBlank(?trip) && ({date_in_interval_expr}) ) "  
               f"{ignore_if_empty('}}', graph_name)} "
            "}"
        )


class DescribeTripIntent(Intent):
    def nl_description(self):
        return 'question is about getting trip summary'

    def __init__(self, **kwargs):
        kwargs['params_definitions'] = [
            IntentParam(param_id='trip_id', meaning='trip ID')
        ]

        super().__init__(**kwargs)

    def as_sparql(self, graph_name: Optional[str] = None) -> Optional[str]:
        return (
            f"{declare_prefixes(TRIP, TRIPUI)} "
             "CONSTRUCT { "
                 f"{TRIPUI.abbr}:TripSummary a {TRIPUI.abbr}:View ;"
                     f"{TRIPUI.abbr}:containsTrip ?trip . "
             "} "
             "WHERE { "
                f"{ignore_if_empty('GRAPH <{}> {{', graph_name)} "
                    f"?trip a {TRIP.abbr}:Trip ; "
                        f"{TRIP.abbr}:hasTripID \"{self.get_param('trip_id').value}\" . "
                    "FILTER (!isBlank(?trip)) "
                f"{ignore_if_empty('}}', graph_name)} "
             "}"
        )


class TripRouteIntent(Intent):
    def nl_description(self):
        return 'question is about getting a route of specific trip'

    def __init__(self, **kwargs):
        kwargs['params_definitions'] = [
            IntentParam(param_id='trip_id', meaning='trip ID')
        ]

        super().__init__(**kwargs)

    def as_sparql(self, graph_name: Optional[str] = None) -> Optional[str]:
        return (
            f"{declare_prefixes(TRIP, TRIPUI)} "
             "CONSTRUCT { "
                 f"{TRIPUI.abbr}:TripRouteSummary a {TRIPUI.abbr}:View ;"
                     f"{TRIPUI.abbr}:containsTrip ?trip ; "
                     f"{TRIPUI.abbr}:containsRoute ?route . "
             "} "
             "WHERE { "
                f"{ignore_if_empty('GRAPH <{}> {{', graph_name)} "
                    f"?trip a {TRIP.abbr}:Trip ; "
                        f"{TRIP.abbr}:hasTripID \"{self.get_param('trip_id').value}\" . "
                    "OPTIONAL { "
                        f"?trip {TRIP.abbr}:hasRoute ?route . "
                    "} "
                    "FILTER (!isBlank(?trip)) "
                f"{ignore_if_empty('}}', graph_name)} "
             "}"
        )


class ListDriverTripsIntent(Intent):
    def nl_description(self):
        return 'question is about getting all trips of a specified driver'

    def __init__(self, **kwargs):
        if 'params_definitions' not in kwargs:
            kwargs['params_definitions'] = []

        kwargs['params_definitions'] += [
            IntentParam(
                param_id='driver_id', meaning='driver ID',
                alternative=IntentParam(
                    param_id='driver_person',
                    meaning='driver first and last names',
                    required=False,
                    converter=lambda x: HumanNameNormalized(full_name=(x['name'] if x['name'] else '')) if (x and 'name' in x) else None
                )
            )
        ]

        super().__init__(**kwargs)

    def _where_criteria(self) -> str:
        driver_person = self.get_param('driver_person')

        fn = driver_person.value.first if driver_person and not driver_person.is_empty else None
        ln = driver_person.value.last if driver_person and not driver_person.is_empty else None

        if not self.get_param('driver_id').is_empty:
            return (
                f"?driver {TRIP.abbr}:hasDriverID ?driver_id . "
                f"FILTER (!isBlank(?trip) && (?driver_id = \"{self.get_param('driver_id').value}\")) "
            )
        elif fn or ln:
            fn_and_ln_expr = self.sparql_and(
                ignore_if_empty('lcase(?ln)=\"{}\"', ln),
                ignore_if_empty('lcase(?fn)=\"{}\"', fn)
            )

            ln_and_fn_expr = self.sparql_and(
                ignore_if_empty('lcase(?fn)=\"{}\"', ln),
                ignore_if_empty('lcase(?ln)=\"{}\"', fn)
            )

            return (
                "OPTIONAL { "
                    f"?driver {TRIP.abbr}:hasFirstName ?fn . "
                "} "
                "OPTIONAL { "
                    f"?driver {TRIP.abbr}:hasLastName ?ln ."
                "} "
               f"FILTER ( !isBlank(?trip) && (({fn_and_ln_expr}) || ({ln_and_fn_expr})) )"
            )

    def as_sparql(self, graph_name: Optional[str] = None) -> Optional[str]:
        return (
            f"{declare_prefixes(TRIP, TRIPUI, TIME, XSD)} "
             "CONSTRUCT { "
                 f"{TRIPUI.abbr}:TripsSummaryList a {TRIPUI.abbr}:View ;"
                     f"{TRIPUI.abbr}:containsTrip ?trip . "
             "} "
             "WHERE { "
                f"{ignore_if_empty('GRAPH <{}> {{', graph_name)} "
                    f"?trip a {TRIP.abbr}:Trip ; "
                          f"{TRIP.abbr}:drivenBy ?driver . "
                    f"{self._where_criteria()} "
                f"{ignore_if_empty('}}', graph_name)} "
             "}"
        )


class DriverTripsOnDateIntent(ListDriverTripsIntent):
    def nl_description(self):
        return "question is about listing all driver's " \
               "trips started at a specified date"

    def __init__(self, **kwargs):
        kwargs['params_definitions'] = [
            IntentParam(
                param_id='date',
                meaning='trip date',
                converter=lambda x: to_utc_iso_format_day_interval(x) if x else None
            )
        ]

        super().__init__(**kwargs)

    def _where_criteria(self) -> str:
        interval = self.get_param('date').value
        start = interval['start']
        end = interval['end']

        date_in_interval_expr = self.sparql_and(
            f"?ts >= \"{start}\"^^{XSD.abbr}:dateTime",
            f"?ts <= \"{end}\"^^{XSD.abbr}:dateTime"
        )

        criteria = (f"?trip {TIME.abbr}:hasBeginning ?beg . "
                    f"?beg {TRIP.abbr}:hasTimestamp ?ts . ")
        criteria += super()._where_criteria()
        criteria += f" FILTER ({date_in_interval_expr} ) "
        return criteria


class TripsWithEventOnDateIntent(Intent):
    def nl_description(self):
        return "question is about listing all driver's trips started at a " \
               "specified date which have a specific event"

    def __init__(self, **kwargs):
        kwargs['params_definitions'] = [
            IntentParam(
                param_id='date',
                meaning='trip date',
                required=False,
                converter=lambda x: to_utc_iso_format_day_interval(x) if x else None
            ),
            IntentParam(
                param_id='refpoint_over-speed',
                meaning='"driver was over speeding" event',
                alternative=IntentParam(
                    param_id='refpoint_hard-brake',
                    meaning='"driver was braking hard" event',
                    required=False,
                    alternative=IntentParam(
                        param_id='refpoint_stopped',
                        meaning='"driver has stopped" event',
                        required=False
                    )
                )
            )
        ]

        super().__init__(**kwargs)

    def _where_criteria(self) -> str:
        interval = self.get_param('date').value
        criteria = ""

        if interval:
            start = interval['start']
            end = interval['end']

            date_in_interval_expr = self.sparql_and(
                f"?tripTS >= \"{start}\"^^{XSD.abbr}:dateTime",
                f"?tripTS <= \"{end}\"^^{XSD.abbr}:dateTime"
            )

            criteria = (f"?trip {TIME.abbr}:hasBeginning ?beg . "
                        f"?beg {TRIP.abbr}:hasTimestamp ?tripTS . ")
            criteria += f" FILTER ({date_in_interval_expr} ) "

        return criteria

    def as_sparql(self, graph_name: Optional[str] = None) -> Optional[str]:
        if self.get_param('refpoint_over-speed').value:
            event_type = 'DriverOverspeedingEvent'
        elif self.get_param('refpoint_hard-brake').value:
            event_type = 'DriverHardBrakingEvent'
        elif self.get_param('refpoint_stopped').value:
            event_type = 'DriverStoppedEvent'
        else:
            event_type = 'Event'

        return (
            f"{declare_prefixes(TRIP, TRIPUI, TIME, XSD, GEOSPARQL, RDFS)} "
             "CONSTRUCT { "
                 f"{TRIP.abbr}:{event_type} {RDFS.abbr}:label ?eventDescr . "
                 f"{TRIPUI.abbr}:TripsEventsSummaryList a {TRIPUI.abbr}:View ;"
                     f"{TRIPUI.abbr}:containsTrip ?trip . "
                 f"?trip {TRIP.abbr}:hasEvent ?mp; "
                     #f"{TRIP.abbr}:hasLocation ?mpRoadSeg ; "
                     #f"{TRIP.abbr}:hasLocation ?mpPoint ; "
                     f"{TRIP.abbr}:hasAbsLocation ?aggrShape ; "
                     f"{TRIP.abbr}:factor ?mp. "
             "} "
             "WHERE { "
                f"{ignore_if_empty('GRAPH <{}> {{', graph_name)} "
                    f"{TRIP.abbr}:{event_type} {RDFS.abbr}:label ?eventDescr . "
                    f"?trip a {TRIP.abbr}:Trip ; "
                          f"{TRIP.abbr}:hasRoute ?route . "
                    f"?route a {TRIP.abbr}:Trace ; "
                          f"{TRIP.abbr}:hasMotionStep ?mp . "
                    f"?mp a {TRIP.abbr}:{event_type} . "
                    # f"OPTIONAL {{ ?mp {GEOSPARQL.abbr}:asWKT ?mpPoint }} "
                    # f"OPTIONAL {{ ?mp {TRIP.abbr}:onRoadSegment ?mpRoadSeg }} "
                    f"OPTIONAL {{ ?mp {TRIP.abbr}:hasShape ?aggrShape }} "
                    f"{self._where_criteria()} "
                f"{ignore_if_empty('}}', graph_name)} "
             "}"
        )


class TripEventLocationIntent(Intent):
    def nl_description(self):
        return "question is about getting route locations of " \
               "specific trip on which the trip has a specific event"

    def __init__(self, **kwargs):
        kwargs['params_definitions'] = [
            IntentParam(param_id='trip_id', meaning='trip ID'),
            IntentParam(
                param_id='refpoint_over-speed',
                meaning='"driver was over speeding" event',
                alternative=IntentParam(
                    param_id='refpoint_hard-brake',
                    meaning='"driver was braking hard" event',
                    required=False,
                    alternative=IntentParam(
                        param_id='refpoint_stopped',
                        meaning='"driver has stopped" event',
                        required=False
                    )
                )
            ),
            IntentParam(
                param_id='refpoint_road-segment',
                meaning='all road segments on which event has occurred',
                alternative=IntentParam(
                    param_id='refpoint_street-names',
                    meaning='all street names where event has occurred',
                    required=False,
                    alternative=IntentParam(
                        param_id='refpoint_road-names',
                        meaning='all road names on which event has occurred',
                        required=False,
                        alternative=IntentParam(
                            param_id='refpoint_map-points',
                            meaning='all route points where event has occurred',
                            required=False,
                            alternative=IntentParam(
                                param_id='refpoint_location',
                                meaning='all location where event has occurred',
                                required=False
                            )
                        )
                    )
                )
            )
        ]

        super().__init__(**kwargs)

    def as_sparql(self, graph_name: Optional[str] = None) -> Optional[str]:
        if self.get_param('refpoint_over-speed').value:
            event_type = 'DriverOverspeedingEvent'
        elif self.get_param('refpoint_hard-brake').value:
            event_type = 'DriverHardBrakingEvent'
        elif self.get_param('refpoint_stopped').value:
            event_type = 'DriverStoppedEvent'
        else:
            event_type = 'Event'

        # is_road_segment_loc = None
        # is_street_names_loc = None
        # is_road_names_loc = None
        # is_map_points_loc = None
        # is_location = None
        #
        # if self.get_param('refpoint_road-segment').value:
        #     is_road_segment_loc = True
        # elif self.get_param('refpoint_street-names').value:
        #     is_street_names_loc = True
        # elif self.get_param('refpoint_road-names').value:
        #     is_road_names_loc = True
        # elif self.get_param('refpoint_map-points').value:
        #     is_map_points_loc = True
        # elif self.get_param('refpoint_location').value:
        #     is_location = True

        return (
            f"{declare_prefixes(TRIP, TRIPUI, TIME, XSD, GEOSPARQL, RDFS)} "
             "CONSTRUCT { "
                 f"{TRIP.abbr}:{event_type} {RDFS.abbr}:label ?eventDescr . "
                 f"{TRIPUI.abbr}:TripEventsListView a {TRIPUI.abbr}:View ; "
                     f"{TRIPUI.abbr}:containsTrip ?trip . "
                 f"?trip {TRIP.abbr}:hasEvent ?mp; "
                     f"{TRIP.abbr}:hasLocationName ?roadName; "
                     f"{TRIP.abbr}:hasAbsLocation ?aggrShape; "
                     # f"{ignore_if_empty(TRIP.abbr + ':hasLocation ?segShape ; ', True)}"
                     # f"{ignore_if_empty(TRIP.abbr + ':hasLocation ?mpPoint ; ', is_map_points_loc)}"
                     f"{TRIP.abbr}:factor ?mp."
             "} "
             "WHERE { "
                f"{ignore_if_empty('GRAPH <{}> {{', graph_name)} "
                    f"{TRIP.abbr}:{event_type} {RDFS.abbr}:label ?eventDescr . "
                    f"?trip a {TRIP.abbr}:Trip ; "
                          f"{TRIP.abbr}:hasTripID \"{self.get_param('trip_id').value}\" ; "
                          f"{TRIP.abbr}:hasRoute ?route . "
                    f"?route a {TRIP.abbr}:Trace ; "
                          f"{TRIP.abbr}:hasMotionStep ?mp . "
                    f"?mp a {TRIP.abbr}:{event_type}, {TRIP.abbr}:RoadMatchedMotionStep ; "
                          f"{TRIP.abbr}:onRoadSegment ?roadSeg ."
                    f"OPTIONAL {{ ?roadSeg {TRIP.abbr}:hasRoadName ?roadName }} "
                    # f"OPTIONAL {{ ?roadSeg {TRIP.abbr}:hasShape ?segShape }} "
                    # f"OPTIONAL {{ ?mp {GEOSPARQL.abbr}:asWKT ?mpPoint }} "
                    f"OPTIONAL {{ ?mp {TRIP.abbr}:hasShape ?aggrShape }} "
                f"{ignore_if_empty('}}', graph_name)} "
             "}"
        )


class TripLocationsIntent(Intent):
    def nl_description(self):
        return "question is about describing specified locations covered by a specific trip"

    def __init__(self, **kwargs):
        kwargs['params_definitions'] = [
            IntentParam(param_id='trip_id', meaning='trip ID'),
            IntentParam(
                param_id='refpoint_road-segment',
                meaning='all road segments on which event has occurred',
                alternative=IntentParam(
                    param_id='refpoint_street-names',
                    meaning='all street names where event has occurred',
                    required=False,
                    alternative=IntentParam(
                        param_id='refpoint_road-names',
                        meaning='all road names on which event has occurred',
                        required=False,
                        alternative=IntentParam(
                            param_id='refpoint_map-points',
                            meaning='all route points where event has occurred',
                            required=False,
                            alternative=IntentParam(
                                param_id='refpoint_location',
                                meaning='all location where event has occurred',
                                required=False
                            )
                        )
                    )
                )
            )
        ]

        super().__init__(**kwargs)

    def as_sparql(self, graph_name: Optional[str] = None) -> Optional[str]:
        # is_road_segment_loc = None
        # is_street_names_loc = None
        # is_road_names_loc = None
        # is_location = None
        #
        # if self.get_param('refpoint_road-segment').value:
        #     is_road_segment_loc = True
        # elif self.get_param('refpoint_street-names').value:
        #     is_street_names_loc = True
        # elif self.get_param('refpoint_road-names').value:
        #     is_road_names_loc = True
        # elif self.get_param('refpoint_location').value:
        #     is_location = True

        return (
            f"{declare_prefixes(TRIP, TRIPUI, TIME, XSD, GEOSPARQL)} "
             "CONSTRUCT { "
                 f"{TRIPUI.abbr}:TripLocationsView a {TRIPUI.abbr}:View ;"
                     f"{TRIPUI.abbr}:containsTrip ?trip . "
                 f"?trip {TRIP.abbr}:hasLocation ["
                    f"{TRIP.abbr}:hasLocationName ?roadName;"
                    f"{TRIP.abbr}:hasAbsLocation ?segShape"
                 "]"
             "} "
             "WHERE { "
                f"{ignore_if_empty('GRAPH <{}> {{', graph_name)} "
                    f"?trip a {TRIP.abbr}:Trip ; "
                          f"{TRIP.abbr}:hasTripID \"{self.get_param('trip_id').value}\" ; "
                          f"{TRIP.abbr}:hasRoute ?route . "
                    f"?route a {TRIP.abbr}:Trace ; "
                          f"{TRIP.abbr}:hasMotionStep ?mp . "
                    f"?mp a {TRIP.abbr}:RoadMatchedMotionStep ; "
                          f"{TRIP.abbr}:onRoadSegment ?roadSeg ."
                    f"OPTIONAL {{ ?roadSeg {TRIP.abbr}:hasRoadName ?roadName }} "
                    f"OPTIONAL {{ ?roadSeg {TRIP.abbr}:hasShape ?segShape }} "
                f"{ignore_if_empty('}}', graph_name)} "
             "}"
        )
