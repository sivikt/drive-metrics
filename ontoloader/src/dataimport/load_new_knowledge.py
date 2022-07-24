import csv
import logging
import io
import random
import uuid

from datetime import datetime

from typing import List, Set, Dict, Optional

from dbapi.graphdb_api import GraphDBApi, GraphDBApiException
from dbapi.prefixes import (
    declare_prefixes,
    TRIP,
    XSD,
    TIME,
    OWL,
    GEOSPARQL,
    SF
)

from utils.date import to_utc
from utils.formatting import ignore_if_empty
from utils.timer import create_elapsed_timer_str

from .autology import (
    define_resources,
    DriverRes,
    VehicleRes,
    TripRes,
    RoadSegmentRes,
    RouteRes,
    TimeRes,
    NodeRes,
    MotionSegmentRes,
    GeoLine,
    GeoPoint
)

from neomodel import db
from neomodel.contrib.spatial_properties import PointProperty
from shared.db import Trip, RouteSegment, Segment, Node
from shared.db.trip_L1_labels import TripOntologyRecord


logger = logging.getLogger(__name__)


class OntologyVersionInfo:
    def __init__(self, latest_write_date: datetime, latest_trip_id: str):
        self._latest_trip_id = latest_trip_id
        self._latest_write_date = latest_write_date
    
    def __str__(self):
        return f"(latest_trip_id={self._latest_trip_id}, latest_write_date={self._latest_write_date.isoformat()})"
    
    @property
    def latest_trip_id(self):
        return self._latest_trip_id

    @property
    def latest_write_date(self):
        return self._latest_write_date
    
    
class BatchUpdate:
    def __init__(self, data_graph_name: str, trips: List[Trip], curr_ontology_version: OntologyVersionInfo):
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

        self.data_graph_name = data_graph_name

        self.trips = trips
        self.curr_ontology_version = curr_ontology_version
        self.next_ontology_version = OntologyVersionInfo(latest_trip_id=trips[-1].trip_id, latest_write_date=trips[-1].write_date)

        self.logger.info(
            'Got batch of %s new trips. Current ontology version %s. Next ontology version %s',
            len(trips),
            self.curr_ontology_version,
            self.next_ontology_version
        )

        self.road_segments_res_cache = {}  # type: Dict[str, RoadSegmentRes]
        self.segment_nodes_res_cache = {}  # type: Dict[NodeRes, NodeRes]
        self.trips_resources = self._create_trip(trips)

    def get_next_ontology_version(self):
        return self.next_ontology_version

    def _create_trip(self, trips: List[Trip]):
        sw = create_elapsed_timer_str('sec')

        trips_resources = []  # List[TripRes]

        drivers_res = [
            DriverRes(driver_id='7AB258700', first_name='John', last_name='Smith'),
            DriverRes(driver_id='8IB258702', first_name='Rebecca', last_name='Maxwell'),
            DriverRes(driver_id='9HB258703', first_name='Nicholas', last_name='Browning')
        ]

        vehicles_res = [
            VehicleRes(vehicle_id='B886AJR'),
            VehicleRes(vehicle_id='11GJ7819IT'),
            VehicleRes(vehicle_id='20304EMGN')
        ]

        for trip in trips:
            try:
                self._update_road_segments_cache(trip)

                driver_res = random.choice(drivers_res)
                vehicle_res = random.choice(vehicles_res)
                route_res = self._create_trip_route(trip)

                trip_res = TripRes(
                    trip_id=trip.trip_id,
                    average_speed=trip.avg_speed,
                    duration_in_sec=trip.duration,
                    route=route_res,
                    driver=driver_res,
                    vehicle=vehicle_res,
                    began_at=TimeRes(
                         at=trip.start_time,
                         at_tz_id=trip.start_local_tz,
                         individual_name=str(uuid.uuid4())
                    ),
                    end_at=TimeRes(
                         at=trip.end_time,
                         at_tz_id=trip.end_local_tz,
                         individual_name=str(uuid.uuid4())
                    )
                )

                trips_resources.append(trip_res)

            except Exception as ex:
                self.logger.exception('Failed to created TripRes from raw trip %s', trip.trip_id)
                raise ex


        self.logger.debug('Created %s TripRes in %s', len(trips_resources), sw())

        return trips_resources

    def _set_l1_labels(self, category: List[str], category_indexes: List[int], out_l1_labels: Set[str]):
        for cat_idx in category_indexes:
            out_l1_labels.add(category[cat_idx])

    def _create_trip_route(self, trip: Trip):
        motion_segments_res = []  # type: List[MotionSegmentRes]
        mmatch_points_all = []    # type: List[GeoPoint]

        sw = create_elapsed_timer_str('sec')

        ordered_rss = trip.route_segments.all()  # type: List[RouteSegment]
        ordered_rss = sorted(ordered_rss, key=lambda x: int(x.route_segment_id.split('#')[1]))

        self.logger.debug('Got %s route segments for trip_id=%s in %s', len(ordered_rss), trip.trip_id, sw())

        sw = create_elapsed_timer_str('sec')

        for i, rs in enumerate(ordered_rss):
            segment_id = rs.segment[0].segment_id  # TODO performance issue
            road_seg_res = self.road_segments_res_cache[segment_id]
            road_seg_res.set_speed_limit_mps(rs.speed_limit)

            if rs.max_speed is not None and rs.speed_limit and (rs.max_speed > rs.speed_limit):
                over_speed_mps = rs.max_speed - rs.speed_limit
            else:
                over_speed_mps = None

            l1_labels = set()  # type: Set[str]
            self._set_l1_labels(
                category=TripOntologyRecord.THROTTLE_CATEGORY,
                category_indexes=rs.throttle_categories,
                out_l1_labels=l1_labels
            )
            self._set_l1_labels(
                category=TripOntologyRecord.BRAKE_CATEGORY,
                category_indexes=rs.brake_categories,
                out_l1_labels=l1_labels
            )
            self._set_l1_labels(
                category=TripOntologyRecord.STEERING_CATEGORY,
                category_indexes=rs.steering_categories,
                out_l1_labels=l1_labels
            )
            self._set_l1_labels(
                category=TripOntologyRecord.SPEED_CATEGORY,
                category_indexes=rs.speed_categories,
                out_l1_labels=l1_labels
            )
            self._set_l1_labels(
                category=TripOntologyRecord.DTHROTTLE_CATEGORY,
                category_indexes=rs.dthrottle_categories,
                out_l1_labels=l1_labels
            )
            self._set_l1_labels(
                category=TripOntologyRecord.DBRAKE_CATEGORY,
                category_indexes=rs.dbrake_categories,
                out_l1_labels=l1_labels
            )
            self._set_l1_labels(
                category=TripOntologyRecord.DSTEERING_CATEGORY,
                category_indexes=rs.dsteering_categories,
                out_l1_labels=l1_labels
            )
            self._set_l1_labels(
                category=TripOntologyRecord.DSPEED_CATEGORY,
                category_indexes=rs.dspeed_categories,
                out_l1_labels=l1_labels
            )
            self._set_l1_labels(
                category=TripOntologyRecord.ACC_LAT_CATEGORY,
                category_indexes=rs.acc_lat_categories,
                out_l1_labels=l1_labels
            )
            self._set_l1_labels(
                category=TripOntologyRecord.ACC_LON_CATEGORY,
                category_indexes=rs.acc_lon_categories,
                out_l1_labels=l1_labels
            )
            self._set_l1_labels(
                category=TripOntologyRecord.ACC_VERT_CATEGORY,
                category_indexes=rs.acc_vert_categories,
                out_l1_labels=l1_labels
            )

            mmatch_points = [GeoPoint(latitude=p.latitude, longitude=p.longitude) for p in rs.matched_points] if rs.matched_points else []
            mmatch_points_all += mmatch_points

            mp_res = MotionSegmentRes(
                unique_suffix=i,
                trip_id=trip.trip_id,
                road_segment=road_seg_res,
                shape=road_seg_res.shape,
                min_speed_mps=rs.min_speed,
                max_speed_mps=rs.max_speed,
                avg_speed_mps=rs.avg_speed,
                sharp_speed_drop_mps=None,
                over_speed_mps=over_speed_mps,
                l1_labels=l1_labels,
                points_timestemps=rs.timestamps,
                mmatch_points=mmatch_points,
            )

            motion_segments_res.append(mp_res)

        route_res = RouteRes(
            trip_id=trip.trip_id,
            route_length_meters=trip.distance,
            motion_segments=motion_segments_res,
            mmatch_points=GeoLine(mmatch_points_all),
            first_location_name=trip.start_location,
            last_location_name=trip.end_location
        )

        self.logger.debug('Created RouteRes for trip_id=%s in %s', trip.trip_id, sw())

        return route_res

    def _update_road_segments_cache(self, trip: Trip):
        sw = create_elapsed_timer_str('sec')

        segments = trip.segments.all()  # type: List[Segment]

        self.logger.debug('Got %s segments for trip_id=%s in %s', len(segments), trip.trip_id, sw())

        for seg in segments:  # type: Segment
            road_seg_res = self.road_segments_res_cache.get(seg.segment_id, None)

            if not road_seg_res:
                seg_pts = seg.shape.split(' ') if seg.shape else []
                seg_pts = [GeoPoint(latitude=seg_pts[i], longitude=seg_pts[i + 1]) for i in range(0, len(seg_pts), 2)]
                shape = GeoLine(seg_pts)

                start_node = seg.start_node.get()
                start_node_res = NodeRes(point=GeoPoint(
                    longitude=start_node.coordinates.longitude,
                    latitude=start_node.coordinates.latitude
                ))

                end_node = seg.end_node.get()
                end_node_res = NodeRes(point=GeoPoint(
                    longitude=end_node.coordinates.longitude,
                    latitude=end_node.coordinates.latitude
                ))

                if start_node_res not in self.segment_nodes_res_cache:
                    self.segment_nodes_res_cache[start_node_res] = start_node_res
                else:
                    start_node_res = self.segment_nodes_res_cache[start_node_res]

                if end_node_res not in self.segment_nodes_res_cache:
                    self.segment_nodes_res_cache[end_node_res] = end_node_res
                else:
                    end_node_res = self.segment_nodes_res_cache[end_node_res]

                road_seg_res = RoadSegmentRes(
                    segment_id=seg.segment_id,
                    start=start_node_res,
                    end=end_node_res,
                    length_meters=seg.length,
                    shape=shape,
                    road_name=seg.location,
                    speed_limit_mps=None  # since limit is in route segment
                )

                self.road_segments_res_cache[seg.segment_id] = road_seg_res

        self.logger.debug('Updated road segments cache for trip_id=%s in %s', trip.trip_id, sw())

    def as_SPARQL(self) -> str:
        def_delete_old_version = (
            "DELETE DATA { "
                f"{ignore_if_empty('GRAPH <{}> ', self.data_graph_name)} "
                    f'{TRIP.abbr}:ontologyVersionInfo '
                    f'{TRIP.abbr}:latestTripID "{self.curr_ontology_version.latest_trip_id}" ;'
                    f'{TRIP.abbr}:latestTripTS "{self.curr_ontology_version.latest_write_date.isoformat()}"^^{XSD.abbr}:dateTime .'
                f"{ignore_if_empty('}', self.data_graph_name)}"
            "};"
        ) if self.curr_ontology_version else ''
        
        return (
            f"{declare_prefixes(TIME, XSD, TRIP, OWL, GEOSPARQL, SF)} "
            f"{def_delete_old_version}"
            "INSERT DATA { "
                f"{ignore_if_empty('GRAPH <{}> {{', self.data_graph_name)} "
                    f"{TRIP.abbr}:ontologyVersionInfo a {OWL.abbr}:NamedIndividual ; "
                            f'{TRIP.abbr}:latestTripID "{self.next_ontology_version.latest_trip_id}" ; '
                            f'{TRIP.abbr}:latestTripTS "{self.next_ontology_version.latest_write_date.isoformat()}"^^{XSD.abbr}:dateTime . '
                    f"{define_resources(self.trips_resources)}"
                f"{ignore_if_empty('}}', self.data_graph_name)} "
            "}"
        )


class DataLoader(GraphDBApi):
    def __init__(self,
                 data_graph_name: str,
                 neo4j_endpoint: str,
                 batch_update_size: int,
                 **kwargs):

        super().__init__(**kwargs)

        self.data_graph_name = data_graph_name
        self.batch_update_size = batch_update_size if batch_update_size > 0 else 0
        self.neo4j_endpoint = neo4j_endpoint

    def get_ontology_version(self) -> Optional[OntologyVersionInfo]:
        query = (
            f"{declare_prefixes(TRIP, TIME)} "
             "SELECT ?latestTripID ?latestTripTS "
             "WHERE { "
                f"{ignore_if_empty('GRAPH <{}> {{', self.data_graph_name)} "
                    f"{TRIP.abbr}:ontologyVersionInfo a {OWL.abbr}:NamedIndividual ; "
                        f"{TRIP.abbr}:latestTripTS ?latestTripTS ; "
                        f"{TRIP.abbr}:latestTripID ?latestTripID . "
                f"{ignore_if_empty('}}', self.data_graph_name)} "
             "}"
        )

        result = self.query(sparql=query)

        if result['format'] == 'text/csv':
            reader = list(csv.DictReader(io.StringIO(result['result'])))
            assert len(reader) < 2
            if reader:
                return OntologyVersionInfo(
                    latest_trip_id=reader[0]['latestTripID'], 
                    latest_write_date=to_utc(reader[0]['latestTripTS'])
                )
            else:
                return None
        else:
            raise GraphDBApiException('Unexpected format ' + result['format'])

    def sync(self):
        db.set_connection(self.neo4j_endpoint)

        ontology_version = self.get_ontology_version()
        sw = create_elapsed_timer_str('sec')

        if ontology_version:
            trips = Trip.nodes.filter(write_date__gte=ontology_version.latest_write_date)  # type: List[Trip]
        else:
            trips = Trip.nodes.all()

        self.logger.info('Got %s new trips in %s', len(trips), sw())

        if trips:
            trips = sorted(trips, key=lambda x: (x.write_date, x.trip_id))

            if ontology_version is not None:
                assert trips[0].write_date >= ontology_version.latest_write_date
                # skip already added trips
                trips = [t for t in trips if (t.write_date > ontology_version.latest_write_date) or (t.trip_id > ontology_version.latest_trip_id)]

            batch_sz = self.batch_update_size if self.batch_update_size > 0 else len(trips)

            trips_batches = [trips[i:i+batch_sz] for i in range(0, len(trips), batch_sz)]

            try:
                for trips_batch in trips_batches:
                    if trips_batch:
                        batch_update = BatchUpdate(
                            data_graph_name=self.data_graph_name,
                            trips=trips_batch,
                            curr_ontology_version=ontology_version
                        )
                        update_sparql = batch_update.as_SPARQL()

                        self.update_in_transaction(sparql=update_sparql)

                        ontology_version = batch_update.get_next_ontology_version()
                    else:
                        self.logger.info('Got 0 new trips')
            finally:
                db.driver.close()
