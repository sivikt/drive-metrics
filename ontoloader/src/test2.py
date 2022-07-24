from dataimport.autology import (
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

node_res1 = NodeRes(point=GeoPoint(
    longitude=-121.87949,
    latitude=37.41458
))

node_res2 = NodeRes(point=GeoPoint(
    longitude=-121.87949,
    latitude=37.41458
))


print(node_res1 == node_res2)


str2 = '' + str(node_res1.point.longitude).replace('-', 'n').replace('.', '_') + str(node_res1.point.latitude).replace('-', 'n').replace('.', '_')
print(str2)


