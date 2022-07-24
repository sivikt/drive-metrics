import pytz
import uuid
import logging

from datetime import datetime
from timezonefinder import TimezoneFinder

from typing import List, Set, Optional

from dbapi.prefixes import (
    declare_prefixes,
    TRIP,
    XSD,
    TIME,
    GEOSPARQL,
    OWL,
    SF
)

from utils.formatting import ignore_if_empty


class GeoPoint:
    def __init__(self,
                 latitude: float,
                 longitude: float):
        self._longitude = longitude
        self._latitude = latitude

    def __eq__(self, obj):
        return isinstance(obj, GeoPoint) and (obj.longitude == self.longitude) and (obj.latitude == self.latitude)

    def __hash__(self):
        return hash((self._latitude, self._longitude))

    @property
    def longitude(self):
        return self._longitude

    @property
    def latitude(self):
        return self._latitude

    def as_WKT(self):
        return f'POINT ({self.longitude} {self.latitude})'


class GeoLine:
    def __init__(self, points: List[GeoPoint]):
        self.points = points if points else []

    def __getitem__(self, key):
        return self.points[key]

    def as_WKT(self):
        pairs = [f'{p.longitude} {p.latitude}' for p in self.points]
        return f"LINESTRING ({','.join(pairs)})"


class Resource:
    def __init__(self, individual_name: Optional[str] = None):
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

        self._is_anonymous = True if individual_name is None else False
        self.id = str(uuid.uuid4())
        self._individual_name = individual_name
        self._is_defined = False

    @property
    def individual_name(self) -> str:
        return self._individual_name

    @property
    def is_anonymous(self) -> bool:
        return self._is_anonymous

    @property
    def IRI(self) -> str:
        return f"_:{self.id}" if self.is_anonymous else f"{TRIP.abbr}:{self.individual_name}"

    def get_definition(self) -> str:
        return ""

    def define_once(self) -> str:
        if self._is_defined:
            return ''
        else:
            return self.get_definition()


def define_resources(resources: List[Resource]):
    definitions = ''
    for res in resources:
        definitions += res.define_once()
    return definitions


class TimeRes(Resource):
    def __init__(self,
                 at: datetime,
                 at_tz_id: str,
                 **kwargs):
        super().__init__(**kwargs)

        self.logger.debug('Creating instance using params individual_name=%s, at=%s, at_tz_id=%s',
                          self.individual_name,
                          at,
                          at_tz_id)

        self.at = at.astimezone(pytz.utc).isoformat()
        self.at_tz_id = at_tz_id

        try:
            #  When using None and the datetime matches the moment of the DST change pytz
            #  does not know how to handle the datetime and you get one of the exceptions shown above.
            offset = pytz.timezone(at_tz_id).utcoffset(at.replace(tzinfo=None), is_dst=None)
            self.at_tz_offset = int(offset.total_seconds())
        except pytz.exceptions.NonExistentTimeError:
            # Else just use Standard Time. But I am not sure this workaround is reliable
            offset = pytz.timezone(at_tz_id).utcoffset(at.replace(tzinfo=None), is_dst=False)
            self.at_tz_offset = int(offset.total_seconds())

    def get_definition(self) -> str:
        return (
            f"{self.IRI} a {TIME.abbr}:Instant {', ' + OWL.abbr + ':NamedIndividual' if not self.is_anonymous else ''};"
                f"{TRIP.abbr}:hasTimestamp \"{self.at}\"^^{XSD.abbr}:dateTime ; "
                f"{TRIP.abbr}:hasTZID \"{self.at_tz_id}\" ; "
                f"{TRIP.abbr}:hasTZOffset {self.at_tz_offset} . "
        )


class NodeRes(Resource):
    def __init__(self,
                 # junction_id: int, # HERE promises to add ID in december
                 point: GeoPoint,
                 **kwargs):

        unique_name = (str(point.longitude) + str(point.latitude)).replace('-', 'n').replace('.', '_')
        kwargs['individual_name'] = f"ND_{unique_name}"
        super().__init__(**kwargs)

        #self.logger.debug('Creating instance using params point=%s', point)

        self.point = point

    def __eq__(self, obj):
        return isinstance(obj, NodeRes) and (obj.point == self.point)

    def __hash__(self):
        return hash(self.point)

    def get_definition(self) -> str:
        geometry_iri = f'{TRIP.abbr}:G_{self.individual_name}'
        def_geometry = (
            f"{geometry_iri} a {SF.abbr}:Point, {OWL.abbr}:NamedIndividual ; "
                f"{GEOSPARQL.abbr}:asWKT \"{self.point.as_WKT()}\"^^{GEOSPARQL.abbr}:wktLiteral. "
        )

        return (
            f"{def_geometry}"
            f"{self.IRI} a {TRIP.abbr}:Node, {OWL.abbr}:NamedIndividual ; "
            f"{GEOSPARQL.abbr}:hasGeometry {geometry_iri} . "
        )


class RoadSegmentRes(Resource):
    def __init__(self,
                 segment_id: int,
                 start: NodeRes,
                 end: NodeRes,
                 length_meters: float,
                 shape: GeoLine,
                 road_name: Optional[str] = None,
                 speed_limit_mps: Optional[float] = None,
                 **kwargs):

        kwargs['individual_name'] = f"RDS_{str(segment_id).replace('-', 'n')}"
        super().__init__(**kwargs)

        self.segment_id = segment_id
        self.start = start
        self.end = end
        self._shape = shape
        self.length_meters = length_meters
        self.road_name = road_name
        self.speed_limit_mps = speed_limit_mps

    def set_speed_limit_mps(self, speed_limit_mps: float):
        self.speed_limit_mps = speed_limit_mps

    @property
    def shape(self):
        return self._shape

    def get_definition(self) -> str:
        def_road_name = f"{TRIP.abbr}:hasRoadName \"{self.road_name}\" ; " if self.road_name else ''

        if self.speed_limit_mps is not None:
            restriction_iri = f"{TRIP.abbr}:MSLR_{str(self.segment_id).replace('-', 'n')}"
            def_speed_limit_restriction = (
                f"{restriction_iri} a {TRIP.abbr}:MaxSpeedLimitRestriction, {OWL.abbr}:NamedIndividual ; "
                            f"{TRIP.abbr}:hasSpeedUnit {TRIP.abbr}:meters_per_sec ; "
                            f"{TRIP.abbr}:hasNumericValue {self.speed_limit_mps} . "
            )

            def_road_segment_restriction = f"{TRIP.abbr}:hasRestriction {restriction_iri} ; "
        else:
            def_speed_limit_restriction = ''
            def_road_segment_restriction = ''

        # def_street_names = ''
        # if self.street_names:
        #     for sn in self.street_names:
        #         def_street_names += f"{TRIP.abbr}:includesStreet \"{sn}\" ; " if sn else ''

        return (
            f"{self.start.define_once()}\n"
            f"{self.end.define_once()}\n"
            f"{def_speed_limit_restriction}\n"
            f"{self.IRI} a {TRIP.abbr}:RoadSegment, {OWL.abbr}:NamedIndividual ; "
            f"{TRIP.abbr}:hasSegmentID \"{str(self.segment_id)}\" ; "
            f"{TRIP.abbr}:startsAtNode {self.start.IRI} ; "
            f"{TRIP.abbr}:endsAtNode {self.end.IRI} ; "
            f"{TRIP.abbr}:hasShape \"{self._shape.as_WKT()}\"^^{GEOSPARQL.abbr}:wktLiteral ; "
            f"{def_road_name}"
            f"{def_road_segment_restriction}"
            f"{TRIP.abbr}:hasLinkLength {self.length_meters} . "
        )


class MotionSegmentRes(Resource):
    def __init__(self,
                 trip_id: str,
                 unique_suffix: int,
                 road_segment: RoadSegmentRes,
                 shape: GeoLine,
                 points_timestemps: List[datetime],
                 mmatch_points: List[GeoPoint],
                 min_speed_mps: Optional[float],
                 max_speed_mps: Optional[float],
                 avg_speed_mps: Optional[float],
                 sharp_speed_drop_mps: Optional[float] = None,
                 over_speed_mps: Optional[float] = None,
                 l1_labels: Optional[Set[str]] = None,
                 **kwargs):
        kwargs['individual_name'] = f'SMP_{trip_id}_{unique_suffix}'
        super().__init__(**kwargs)

        self.road_segment = road_segment
        self.shape = shape
        self.min_speed_mps = min_speed_mps
        self.max_speed_mps = max_speed_mps
        self.avg_speed_mps = avg_speed_mps

        self.sharp_speed_drop_mps = sharp_speed_drop_mps
        self.over_speed_mps = over_speed_mps

        self.start_point = mmatch_points[0]
        self.end_point = mmatch_points[-1]

        tf = TimezoneFinder(in_memory=False)

        self.start_time = TimeRes(
            at=points_timestemps[0],
            at_tz_id=tf.timezone_at(lng=self.start_point.longitude, lat=self.start_point.latitude),
            individual_name=str(uuid.uuid4())
        )
        self.end_time = TimeRes(
            at=points_timestemps[-1],
            at_tz_id=tf.timezone_at(lng=self.end_point.longitude, lat=self.end_point.latitude),
            individual_name=str(uuid.uuid4())
        )

        self.l1_labels = l1_labels

    def get_definition(self) -> str:
        def_sharp_speed_drop_mps = f"{TRIP.abbr}:sharpSpeedDropByValue {self.sharp_speed_drop_mps} ; " if self.sharp_speed_drop_mps else ''
        def_over_speed_mps = f"{TRIP.abbr}:overspeedByValue {self.over_speed_mps} ; " if self.over_speed_mps else ''
        def_min_speed_mps = f"{TRIP.abbr}:hasMinSpeed {self.min_speed_mps} ; " if self.min_speed_mps is not None else ''
        def_max_speed_mps = f"{TRIP.abbr}:hasMaxSpeed {self.max_speed_mps} ; " if self.max_speed_mps is not None else ''
        def_avg_speed_mps = f"{TRIP.abbr}:hasAvgSpeed {self.avg_speed_mps} ; " if self.avg_speed_mps is not None else ''

        def_l1_labels = ''
        if self.l1_labels:
            for l1l in self.l1_labels:
                def_l1_labels += f"{TRIP.abbr}:hasL1Label {TRIP.abbr}:{l1l} ; "

        return (
            f"{self.start_time.define_once()}\n"
            f"{self.end_time.define_once()}\n"
            f"{self.road_segment.define_once()}\n"
            f"{self.IRI} a {TRIP.abbr}:MotionSegment, {OWL.abbr}:NamedIndividual ; "
            f"{TRIP.abbr}:onRoadSegment {self.road_segment.IRI} ; "
            f"{TIME.abbr}:hasBeginning {self.start_time.IRI} ; "
            f"{TIME.abbr}:hasEnd {self.end_time.IRI} ; "
            f"{TRIP.abbr}:hasFirstAbsLocation \"{self.start_point.as_WKT()}\"^^{GEOSPARQL.abbr}:wktLiteral ; "
            f"{TRIP.abbr}:hasLastAbsLocation \"{self.end_point.as_WKT()}\"^^{GEOSPARQL.abbr}:wktLiteral ; "
            f"{def_sharp_speed_drop_mps}"
            f"{def_over_speed_mps}"
            f"{def_min_speed_mps}"
            f"{def_max_speed_mps}"
            f"{def_avg_speed_mps}"
            f"{def_l1_labels}"
            f"{TRIP.abbr}:hasShape \"{self.shape.as_WKT()}\"^^{GEOSPARQL.abbr}:wktLiteral . "
        )


class RouteRes(Resource):
    def __init__(self,
                 trip_id: str,
                 route_length_meters: float,
                 first_location_name: str,
                 last_location_name: str,
                 motion_segments: List[MotionSegmentRes],
                 mmatch_points: GeoLine,
                 **kwargs):

        kwargs['individual_name'] = f'RTE_{trip_id}'
        super().__init__(**kwargs)

        self.route_length = route_length_meters
        # self.road_segments = road_segments if road_segments else []
        self.motion_points = motion_segments if motion_segments else []
        self.mmatch_points = mmatch_points

        self.first_abs_location = mmatch_points[0]
        self.last_abs_location = mmatch_points[-1]
        self.first_location_name = first_location_name
        self.last_location_name = last_location_name

    def get_definition(self) -> str:
        def_motion_point = ''
        if self.motion_points:
            for mp in self.motion_points:
                def_motion_point += f"{TRIP.abbr}:hasMotionStep {mp.IRI} ; "

        route_length_iri = f"{TRIP.abbr}:{str(uuid.uuid4())}"
        def_route_length = (
            f"{route_length_iri} a {TRIP.abbr}:Distance, {OWL.abbr}:NamedIndividual ; "
            f"{TRIP.abbr}:hasDistanceUnit {TRIP.abbr}:meters ; "
            f"{TRIP.abbr}:hasNumericValue {self.route_length} . "
        )

        def_first_location_name = ''
        if self.first_location_name:
            def_first_location_name = f'{TRIP.abbr}:hasFirstLocationName "{self.first_location_name}" ;'

        def_last_location_name = ''
        if self.last_location_name:
            def_last_location_name = f'{TRIP.abbr}:hasLastLocationName "{self.last_location_name}" ;'

        return (
            f"{def_route_length}\n"
            f"{define_resources(self.motion_points)}\n"
            f"{self.IRI} a {TRIP.abbr}:Route, {OWL.abbr}:NamedIndividual ; "
            f"{TRIP.abbr}:hasRouteLength {route_length_iri} ; "
            f"{TRIP.abbr}:hasFirstAbsLocation \"{self.first_abs_location.as_WKT()}\"^^{GEOSPARQL.abbr}:wktLiteral ; "
            f"{TRIP.abbr}:hasLastAbsLocation \"{self.last_abs_location.as_WKT()}\"^^{GEOSPARQL.abbr}:wktLiteral ; "
            f"{def_first_location_name}"
            f"{def_last_location_name}"
            f"{def_motion_point}"
            f"{TRIP.abbr}:hasAbsLocations \"{self.mmatch_points.as_WKT()}\"^^{GEOSPARQL.abbr}:wktLiteral . "
        )


class DriverRes(Resource):
    def __init__(self,
                 driver_id: str,
                 first_name: str,
                 last_name: str,
                 **kwargs):
        kwargs['individual_name'] = f'Driver_{driver_id}'
        super().__init__(**kwargs)

        self.driver_id = driver_id
        self.first_name = first_name
        self.last_name = last_name

    def get_definition(self) -> str:
        return (
            f"{self.IRI} a {TRIP.abbr}:Driver, {OWL.abbr}:NamedIndividual ; "
            f"{TRIP.abbr}:hasDriverID \"{self.driver_id}\" ; "
            f"{TRIP.abbr}:hasLastName \"{self.last_name}\" ; "
            f"{TRIP.abbr}:hasFirstName \"{self.first_name}\" ; "
            f"{TRIP.abbr}:hasDriverClass {TRIP.abbr}:B_class_driver . "
        )


class VehicleRes(Resource):
    def __init__(self,
                 vehicle_id: str,
                 **kwargs):
        kwargs['individual_name'] = f'Vehicle_{vehicle_id}'
        super().__init__(**kwargs)

        self.vehicle_id = vehicle_id

    def get_definition(self) -> str:
        return (
            f"{self.IRI} a {TRIP.abbr}:RegularCar, {OWL.abbr}:NamedIndividual ; "
            f"{TRIP.abbr}:hasVehicleID \"{self.vehicle_id}\" . "
        )


class TripRes(Resource):
    def __init__(self,
                 trip_id: str,
                 average_speed: float,
                 duration_in_sec: int,
                 route: RouteRes,
                 driver: DriverRes,
                 vehicle: VehicleRes,
                 began_at: TimeRes,
                 end_at: TimeRes,
                 **kwargs):
        kwargs['individual_name'] = f'Trip_{trip_id}'
        super().__init__(**kwargs)

        self.trip_id = trip_id
        self.average_speed = average_speed
        self.duration_in_sec = duration_in_sec
        self.route = route
        self.driver = driver
        self.vehicle = vehicle
        self.began_at = began_at
        self.end_at = end_at

    def get_definition(self) -> str:
        average_speed_iri = f"{TRIP.abbr}:{str(uuid.uuid4())}"
        def_average_speed = (
            f"{average_speed_iri} a {TRIP.abbr}:Speed, {OWL.abbr}:NamedIndividual ; "
            f"{TRIP.abbr}:hasNumericValue {self.average_speed} ; "
            f"{TRIP.abbr}:hasSpeedUnit {TRIP.abbr}:meters_per_sec . "
        )

        duration_iri = f"{TRIP.abbr}:{str(uuid.uuid4())}"
        def_duration = (
            f"{duration_iri} a {TRIP.abbr}:Duration, {OWL.abbr}:NamedIndividual ; "
            f"{TIME.abbr}:numericDuration {self.duration_in_sec}; "
            f"{TIME.abbr}:unitTime {TIME.abbr}:unitSecond . "
        )

        return (
            f"{def_average_speed}\n"
            f"{def_duration}\n"
            f"{self.began_at.define_once()}\n"
            f"{self.end_at.define_once()}\n"
            f"{self.vehicle.define_once()}\n"
            f"{self.driver.define_once()}\n"
            f"{self.route.define_once()}\n"
            f"{self.IRI} a {TRIP.abbr}:Trip, {OWL.abbr}:NamedIndividual ; "
            f"{TRIP.abbr}:hasTripID \"{self.trip_id}\" ; "
            f"{TRIP.abbr}:hasRoute {self.route.IRI} ; "
            f"{TRIP.abbr}:drivenBy {self.driver.IRI} ; "
            f"{TRIP.abbr}:byVehicle {self.vehicle.IRI} ; "
            f"{TRIP.abbr}:hasAverageSpeed {average_speed_iri} ; "
            f"{TIME.abbr}:hasDuration {duration_iri} ; "
            f"{TIME.abbr}:hasBeginning {self.began_at.IRI} ; "
            f"{TIME.abbr}:hasEnd {self.end_at.IRI} . "
        )
