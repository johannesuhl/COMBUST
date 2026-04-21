"""
Download "amenity:fuel" from OSM by state
Author: maxwell.cook@colorado.edu
"""

import os, time
import geopandas as gpd
import overpy
import geojson

from shapely.geometry import Point, Polygon

t0 = time.time()  # start time

maindir = "/Users/max/Library/CloudStorage/OneDrive-Personal/mcook/"
projdir = os.path.join(maindir, 'earth-lab/opp-urban-fuels/')
out_dir = os.path.join(projdir, 'data/spatial/raw/OSM/')
if not os.path.exists(out_dir):
    os.makedirs(out_dir)

# Initialize the Overpass API
api = overpy.Overpass()

# Load CONUS counties
counties = gpd.read_file(os.path.join(maindir,"data/boundaries/political/TIGER/tl19_us_counties_conus.gpkg"))

# Dissolve by county
counties_ = counties.dissolve(by="GEOID", aggfunc="first").reset_index()
counties_ = counties_.to_crs(epsg=4326)  # ensure WGS projection for lat/lon bounds
print(f"Submitting queries for [{len(counties_)}] county boundaries.")
print(counties_.columns)
print("\n~~~~~~~~~~\n")

osm_nodes = []  # to store nodes (points)
osm_ways = []  # to store ways (lines or polygons)
bad_counties = []  # to store names of any bad counties (throwing errors)
processed_osm_ids = set()  # to track duplicates
nodes_as_ways = set()  # to track nodes which are likely a part of ways

# Loop counties, download
print_freq = int(len(counties_)/10)  # how often to print progress
for idx, row in counties_.iterrows():
    # Gather attributes
    geoid = row['GEOID']  # state FIPS + county FIPS

    # Gather the geometry bounds
    minx, miny, maxx, maxy = row.geometry.bounds

    # Overpass query for "amenity=fuel"
    query = f"""
    [out:json];
    (
      node["amenity"="fuel"]({miny},{minx},{maxy},{maxx});
      way["amenity"="fuel"]({miny},{minx},{maxy},{maxx});
    );
    out body;
    >;
    out skel qt;
    """

    # Attempt the query
    try:
        response = api.query(query)  # submit the query

        # Collect nodes that are part of ways (vertices)
        for way in response.ways:
            for node in way.nodes:
                nodes_as_ways.add(node.id)  # track these

        # collect node features
        for node in response.nodes:
            if node.id not in processed_osm_ids:  # Check for duplicates
                processed_osm_ids.add(node.id)  # Mark OSM ID as processed
                point = geojson.Point((float(node.lon), float(node.lat)))
                is_vertex = node.id in nodes_as_ways  # check if it is part of way
                properties = {
                    "osm_id": node.id,
                    "tags": node.tags,
                    "osm_type": "node",
                    "GEOID": geoid,
                    "vertex": is_vertex  # true if part of way
                }
                osm_nodes.append(geojson.Feature(geometry=point, properties=properties))

        # Process ways (polygons or lines)
        for way in response.ways:
            if way.id not in processed_osm_ids:
                processed_osm_ids.add(way.id)
                # Assume a way is a polygon (you can check geometry if needed)
                if len(way.nodes) >= 3:  # At least 3 points needed to form a polygon
                    coords = [(float(nd.lon), float(nd.lat)) for nd in way.nodes]
                    polygon = Polygon(coords)  # extract the polygon
                    centroid = polygon.centroid  # extract the centroid

                    # Store the centroid geojson
                    point = geojson.Point((centroid.x, centroid.y))
                    properties = {
                        "osm_id": way.id,
                        "tags": way.tags,
                        "osm_type": "way",
                        "GEOID": geoid
                    }
                    osm_ways.append(geojson.Feature(geometry=point, properties=properties))
                    del coords, polygon, centroid, point

    except Exception as e:
        print(f"Error querying gas stations for {geoid} county: {e}")
        bad_counties.append(geoid)

    if (idx + 1) % print_freq == 0 or (idx + 1) == len(counties_):
        percentage = (idx + 1) / len(counties_) * 100
        print(f"\tQueried [{idx + 1}/{len(counties_)} ({percentage:.2f}%)] counties.")

# Merge county files
osm_nodes = geojson.FeatureCollection(osm_nodes)
osm_ways = geojson.FeatureCollection(osm_ways)

# Save nodes, ways, and relations in separate files
geojson_files = {
    "nodes": osm_nodes,
    "ways": osm_ways
}

# Export nodes and ways separately
for osm_type, osm_data in geojson_files.items():
    conus_out_fp = os.path.join(out_dir, f"amenity-fuel_{osm_type}_CONUS_by_County.geojson")
    with open(conus_out_fp, 'w') as f:
        geojson.dump(osm_data, f)

# Create a combined database
osm_nodes_ = [
    node for node in osm_nodes['features'] if not node['properties']['vertex']
]
osm_fuel_stations = geojson.FeatureCollection(osm_nodes_ + osm_ways['features'])
out_fp = os.path.join(out_dir, "amenity-fuel_combined_CONUS_by_County.geojson")
with open(out_fp, 'w') as f:
    geojson.dump(osm_fuel_stations, f)

print("\n~~~~~~~~~~~~~~~~~~\nSuccess!")
t1 = (time.time() - t0) / 60
print(f"\tTotal elapsed time for queries: {t1:.2f} minutes.")