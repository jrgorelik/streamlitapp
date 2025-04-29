import numpy as np
import pandas as pd
import streamlit as st
import sqlalchemy
import googlemaps
import pydeck as pdk
import polyline

engine = sqlalchemy.create_engine("***")
with engine.connect() as conn:
    result = conn.execute(sqlalchemy.text("select * from ref_locations"))

gmaps = googlemaps.Client(key='***')

list_of_rows = []
for row in result:
    list_of_rows.append(row)
ref_locations = pd.DataFrame(list_of_rows)
ref_locations = ref_locations[(ref_locations["latitude"]!=0)&(ref_locations["longitude"]!=0)]
ref_locations.reset_index(inplace=True,drop=True)
ref_locations["city_state"] = ref_locations["city"] + ", " + ref_locations["state"]

ref_locations_dict = {}
for i in range(0,len(ref_locations["latitude"])):
    ref_locations_dict[ref_locations.loc[i,"city_state"]] = {"latitude":ref_locations.loc[i,"latitude"],
                                                         "longitude":ref_locations.loc[i,"longitude"]}

mileage = 0
rail_mileage = None
truck_mileage = None
tonnage = 0
route_geometry = "0"
mileage = st.number_input("Miles: ")
tonnage = st.number_input("Number of tons: ")

origin_city_state = st.selectbox("Origin Location", options=ref_locations["city_state"].sort_values())
dest_city_state = st.selectbox("Destination Location", options=ref_locations["city_state"].sort_values())
default_city_state_value = "11TH AVE NASHVILLE, TN"

if (mileage==0) and (origin_city_state!=default_city_state_value
                     and dest_city_state!=default_city_state_value):
    with engine.connect() as conn:
        result = conn.execute(sqlalchemy.text(
            "SELECT total_distance_miles, ST_AsText(route_geometry) as route_geometry FROM gis.find_shortest_rail_route('{}', '{}')".format(
                origin_city_state,dest_city_state)))
    tmp_df = pd.DataFrame(result.fetchall())
    rail_mileage = tmp_df["total_distance_miles"][0]
    route_geometry = tmp_df["route_geometry"][0]
    truck_mileage = float(gmaps.distance_matrix(origins = (ref_locations_dict[origin_city_state]['latitude'],
                                                         ref_locations_dict[origin_city_state]['longitude']),
                                              destinations = (ref_locations_dict[dest_city_state]['latitude'],
                                                              ref_locations_dict[dest_city_state]['longitude']),
                      mode="driving", units='imperial')['rows'][0]['elements'][0]['distance']['text'][0:-3].replace(",",""))
    truck_directions = gmaps.directions(origin = (ref_locations_dict[origin_city_state]['latitude'],
                                                         ref_locations_dict[origin_city_state]['longitude']),
                                        destination = (ref_locations_dict[dest_city_state]['latitude'],
                                                              ref_locations_dict[dest_city_state]['longitude']),
                                        mode="driving")
    truck_directions_decoded = polyline.decode(truck_directions[0]['overview_polyline']['points'])
    truck_directions_decoded = [[y, x] for x, y in truck_directions_decoded]

st.write("The mileage we are using for the rail calculation is {}".format(rail_mileage if rail_mileage else mileage))
st.write("The mileage we are using for the truck calculation is {}".format(truck_mileage if truck_mileage else mileage))

if route_geometry !="0":
    def parse_wkt_linestring(wkt: str):
        # strip off the "LINESTRING" label and surrounding parentheses
        coords_text = wkt.strip().removeprefix("LINESTRING").strip().strip("()")
        pts = coords_text.split(",")
        return [list(map(float, pt.strip().split())) for pt in pts]


    path = parse_wkt_linestring(route_geometry)
    # st.text(path)
    # 3) Build a pydeck PathLayer
    layer = layer = [pdk.Layer(
    "PathLayer",
    data=[{"name": "Rail Path",
          "path": path}
         ],
    get_path = "path",
    pickable = True,
    get_width=3,
    width_min_pixels=3,
    get_color = '[66, 245, 147, 150]'
),
    pdk.Layer(
    "PathLayer",
    data=[{"name": "Truck Path",
          "path": truck_directions_decoded}
         ],
    get_path = "path",
    pickable = True,
    get_width=3,
    width_min_pixels=3,
    get_color = '[245, 66, 66, 150]')]

    # 4) Center the view on the first point
    initial_view = pdk.ViewState(
        longitude=path[0][0],
        latitude=path[0][1],
        zoom=5
    )

    st.pydeck_chart(pdk.Deck(layers=[layer],
                             initial_view_state=initial_view))

    st.write("Green represents the rail path. Red represents the truck path.")
def most_basic_comparison(tonnage, routes = False, mileage = None, rail_mileage=None, truck_mileage=None):
    if routes:
        rail_total = rail_mileage * tonnage * 16.81/1000
        truck_total = truck_mileage * tonnage * 82.56/1000
    else:
        rail_total = mileage * tonnage * 16.81 / 1000
        truck_total = mileage * tonnage * 82.56 / 1000
    st.write("The shipment will produce {} kg(s) of CO_2 if it is transported via Rail".format(rail_total))
    st.write("The shipment will produce {} kg(s) of CO_2 if it is transported via Truck".format(truck_total))
    st.write("Shipping via Rail will save {} kg(s) of CO_2".format(truck_total-rail_total))
    return None


if mileage == 0:
    if not rail_mileage and not truck_mileage:
        st.write("Please Input values for CO_2 estimates")
    else:
        most_basic_comparison(tonnage, routes = True, mileage = mileage, rail_mileage=rail_mileage, truck_mileage=truck_mileage)
else:
    most_basic_comparison(tonnage, False, mileage, rail_mileage, truck_mileage)
conn.close()