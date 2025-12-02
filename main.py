#Names: Vivian Hernandez & Jenny Zheng

from collections import Counter
import datetime
import re
import math
import sys
import simplekml
from pathlib import Path
from datetime import timedelta, timezone

# RIT's (lat, lon)
RIT = (43.085556, -77.680556)
# Prof's Home
HOUSE = (43.139444, -77.439444)

# max number of points 
MAX_POINTS = 10000


######### STEP 1: Read File #########
def readFile(file_path):
    gps_data = []  # []format 

    try:
        with open(file_path, 'r', encoding='latin1') as f:
            lines = f.read().splitlines()  
            temp_arr = []
            for line in lines[5:]: #Skip teh first 5 lines 
                if not line.strip():
                    continue
                
                # ignore lines with burped gps data
                count = line.count("$GP")
                if count > 1:
                    # print("double found")
                    # print(line)
                    # parts_list = re.findall(r'(\$GP[^$\r\n]*)', line)
                    # for sent in parts_list:
                    #     fields = sent.split(',')
                    #     fields = [p if p != '' else '0' for p in fields]
                    #     temp_arr.append(fields)
                    continue


                parts = line.split(',') #Splits the data by comma
                # print(parts)
                
                parts = [p if p != '' else '0' for p in parts] #makes this an array for the line 
                temp_arr.append(parts)
            gps_data.append(temp_arr)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")

    
    # print(gps_data[0]) #EXAMPLE
    return gps_data

######### STEP 2: CONVERT DATA TO KML FILE #########


####  HELPER FUNCT ####

def safe_float(value):
    # removes any character that isn't a digit or a decimal point 
    cleaned = re.sub(r"[^0-9.]", "", value)
    # returns the cleaned string as a float, otherwise 0.0 if empty str
    return float(cleaned) if cleaned else 0.0

def clean_nmea_field(gps):
    """Remove any non-digit characters from a NMEA field."""
    return ''.join(ch for ch in gps if ch.isdigit())


def nmea_to_decimal(value, direction):
    """
    Converts NMEA ddmm.mmmm (dd is the degrees, mm.mmmm is the decimal minutes)
    to decimal degrees
    Example: 4308.4726, 'N' → 43.141210

    Note: value has to be in str formay 
          NMEA format is fixed -> (d)ddmm.mmmm.
    """
    if '.' in value:
        # must have a . for valid NMEA format
        dec_pos = value.find('.')
        min_start = dec_pos - 2     # last 2 digits before the deimial are the degrees
        # extract the degrees, index 0 to wherever min_start is
        degrees_part = safe_float(value[:min_start])
        # this gets the minutes part 
        min_part = float(value[min_start:])

        # convert to decimal by converting the minutes to decimal and adding degrees
        dec_degrees = degrees_part + (min_part / 60.0)
    else:
        return None #Case: No . found, likely an invalid format
   
    # negate if sourth or west -- standard gps convention
    if direction in ["S", "W"]:
        dec_degrees *= -1

    return dec_degrees

def convert_utc(time):
    """
    Converts to YYYY-MM-DDThh:mm:ssZ
    Example: 144904.500        -> UTC Time: 14:49:04.500 (hhmmss.sss)
    """
    return datetime.datetime.fromtimestamp(time, tz=timezone.utc)


def date_time_conversion(date, time):
    """
    Converts to date time format
    """
    date = clean_nmea_field(date)
    time = clean_nmea_field(time)

    hours = int(time[0:2])
    minutes = int(time[2:4])
    seconds = int(time[4:6])
    
    day = int(date[0:2])
    month = int(date[2:4])
    year = int(date[4:6])
    year += 2000

    dt = datetime.datetime(year, month, day, hours, minutes, seconds)

    date_time = dt.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
    return date_time




def degree_turn(p1, p2):
    """
    Returns turn degrees from point1 to point2
    0 = north
    90 = east
    180 = south
    270 = west
    """
    # convert degrees to radians
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    # get the difference in longitude between the two points
    dlon = lon2 - lon1
    # calculates the east-west component of the bearing
    x = math.sin(dlon) * math.cos(lat2)
    # calculates the north-south component of the bearing 
    y = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dlon)
    # calcluate the angle from north clockwise to the (x,y) point 
    brng = math.atan2(x, y)
    # convert back to degrees
    brng = math.degrees(brng)
    # ensures result is positive 
    return (brng + 360) % 360

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0   # earth's radius in meters
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    diff_lat = math.radians(lat2-lat1)
    diff_lon = math.radians(lon2 - lon1)

    a = math.sin(diff_lat)**2 + math.cos(lat1_rad)*math.cos(lat2_rad)*math.sin(diff_lon/2)**2

    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

def signed_bearing_delta(bearing1, bearing2):
    # returns signed delta in degrees in range -180 and 180
    # Postive = right turn, Negative = left turn
    delta = (bearing2 - bearing1 + 540) % 360 - 180
    return delta

def turn_direction(p1, p2, p3, threshold_deg = 10.0, min_dist = 3.0):
    '''
    p1,p2,p3 are tuples (lat, lon)
    threshold_deg: minimum absolute bearing change to consider a turn
    min_dist: minimum meters between points to avoid noisy bearings
    TODO: if too many false turns raise thresh to 20-30 or increase min dist
    if we start missing gentle turns, lower the threshold
    '''
    lat1, lon1 = p1
    lat2, lon2 = p2
    lat3, lon3 = p3

    # skip if points are too close
    if haversine_m(lat1, lon1, lat2, lon2) < min_dist:
        return "straight"
    if haversine_m(lat2, lon2, lat3, lon3) < min_dist:
        return "straight"

    b1 = degree_turn(p1, p2)    # bearing from p1 to p2
    b2 = degree_turn(p2, p3)    # bearing from p2 to p3

    # diff = (b2 - b1 + 360) % 360    # change in bearing in degrees 

    # if diff > 10 and diff < 180:
    #     return "left"
    # elif diff > 180 and diff < 350:
    #     return "right"
    # else:
    #     return "straight"

    delta = signed_bearing_delta(b1, b2)
    
    if delta > threshold_deg:
        return "right"
    elif delta < -threshold_deg:
        return "left"
    else:
        return "straight"


def read_gprmc(arr):
    """
    Read and convert the gprmc -> Recommended Minimum Navigation Information (navigation/positioning type)
    """
    if len(arr) < 10:
        return None
    
    date_time = date_time_conversion(arr[9],arr[1])
    time = float(arr[1])
    status = arr[2]
    latitude = nmea_to_decimal(arr[3],arr[4])
    longitude = nmea_to_decimal(arr[5],arr[6])
    speed = safe_float(arr[7])
    course = float(arr[8])

    #Error Check: 2 valid args 
    mode = ""
    checkSum = ""
    if len(arr) > 12:
        if '*' in arr[12]:
            parts = arr[12].split('*')
            mode = parts[0]
            checkSum = parts[1] if len(parts) > 1 else ""
        else:
            mode = arr[12]


    if(status == 'V'): return None #Not Valid

    return {
        "date_time": date_time,   # ISO 8601 time 
        "time":time,
        "status": status,         #Status: A = valid, V = void              
        "latitude": latitude,                  
        "longitude": longitude,              
        "speed": speed,           #Speed over ground in knots              
        "course": course,         #Track angle in degrees                            
        "mode": mode,             #A = Autonomous, D = Differential, E = Estimated, N = Data not valid                   
        "checksum": checkSum      #XOR of all characters between $ and *               
    }



def read_gpgga(arr):
    """
    Read and convert the gprmc -> Global Positioning System Fix Data (fix/precision type)
    
    162.6             -> Altitude above mean sea level (meters)
    M                 -> Units for altitude: M = meters
    -34.4             -> Height of geoid (mean sea level) above WGS84 ellipsoid (meters)
    M                 -> Units for geoid separation: M = meters
    """
    utc_time = convert_utc(float(arr[1]))
    latitude = nmea_to_decimal(arr[2],arr[3])
    longitude = nmea_to_decimal(arr[4],arr[5])
    fix_quality = int(arr[6])
    num_satellites = int(arr[7])
    hdop = float(arr[8])
    altitude = float(arr[9])
    geoid_height = arr[11]
    dgps_update = arr[13] if len(arr) > 12 else ''
    dgps_station = arr[14] if len(arr) > 13 else ''
    checksum = arr[14].replace("*","") if len(arr) > 14 else ""

    return {
        "utc_time": utc_time,               #Time Format: 14:49:04.750 (hhmmss.sss)        
        "latitude": latitude,                
        "longitude": longitude,               
        "fix_quality": fix_quality,         #0 = invalid, 1 = GPS fix, 2 = DGPS fix
        "num_satellites": num_satellites,
        "hdop": hdop,                       #Horizontal Dilution of Precision (HDOP)
        "altitude": altitude,          
        "geoid_height": geoid_height,       #Units for altitude
        "dgps_update": dgps_update,
        "dgps_station": dgps_station,
        "checksum": checksum                #XOR of all characters between $ and *
    }


def get_start_and_end_index(all_info):
    """
    returns the start and end index of when the car first starts moving and 
    last stops moving
    Note: speed is in knots
    """
    # using 0.8 m/s or 1.55 knots for the threshold for moving vehicles
    MOVING = 2
    start = None
    end = None
    for index, info in enumerate(all_info):
        # print(info)
        if info["speed"] > MOVING:
            start = index
            break
    
    for index, info in enumerate(reversed(all_info)):
        if info["speed"] > MOVING:
            end = len(all_info) - index
            break
    
    # use the points right before and right after motion detected
    if start != 0:
        start -= 1

    return start, end

def estimate_missing(all_info, index):
    """
    get the distance from the current index to the closest location (home or rit)
    and then calculate how long it would have taken to go from current location to
    the closest location at the current speed
    """
    current = all_info[index]
    # speed in knots
    speed = current["speed"]
    
    dist_to_rit = haversine_m(current["latitude"], current["longitude"], RIT[0], RIT[1])

    dist_to_home = haversine_m(current["latitude"], current["longitude"], HOUSE[0], HOUSE[1])

    # get min dist in meters 
    min_dist = min(dist_to_rit, dist_to_home)

    # print("min dist: ", min_dist)

    # speed in meters per second
    speed_ms = speed * 1852 / 3600

    # print("meters per second: ", speed_ms)

    # get the time traveled in seconds
    seconds = min_dist/ speed_ms

    return datetime.timedelta(seconds=seconds)

    

def is_jump(prev, curr, max_speed = 97):
    """
    prev, curr: tuples of (lat, lon, datetime)
    max_speed: maximum plausible speed
    """
    # 97 knots is approx 50 m/s
    # TODO maybe this needs to be swapped
    dist = haversine_m(prev[0], prev[1], curr[0], curr[1])
    time_diff = (curr[2] - prev[2]).total_seconds()
    # print(time_diff)
    
    if time_diff == 0:
        return True  # duplicate timestamp
    
    speed = dist / time_diff  # meters per second
    if speed > max_speed:
        return True  # unrealistically fast -> ignore
    return False


def filter_route(route_coords):
    """
     if vehicle is traveling nearly straight, you can ignore some points on the line

     keep the first and last point and any point where the bearing changes significantly 
    """
    threshold = 3.0
    # if we only have 3 points, we keep them all
    if len(route_coords) < 3:
        return route_coords
    
    filtered = [route_coords[0]]

    for i in range(1, len(route_coords) - 2):
        p1 = (route_coords [i][1],route_coords [i][0])  # lat, lon
        p2 = (route_coords [i+1][1], route_coords [i+1][0])
        p3 = (route_coords [i+2][1], route_coords [i+2][0])

        bearing1 = degree_turn(p1, p2)
        bearing2 = degree_turn(p2, p3)

        deg_change = abs(signed_bearing_delta(bearing1, bearing2))

        if deg_change >= threshold:
            filtered.append(route_coords[i])

        # direction = turn_direction(p1, p2, p3)

        # if direction != "straight":
        #     filtered.append(route_coords[i])

    filtered.append(route_coords[-1])

    return filtered




#### MAIN FILE #####
def makeKMLFile(gps_data):
    """
    
    array of arrays
    """
    STOP_SPEED = 1.0
    MIN_STOP = 1.0
    MOVING = 2
    kml = simplekml.Kml()
 
    #Read in the gps info 
    route_coords = []
    all_info =[]
    # track previous point
    prev_point = None

    for arr in gps_data:

        if arr[0].endswith("GPRMC"):
            rmc = read_gprmc(arr) 

            if rmc is None:
                continue 

            # ignore impossible lat/long
            p_lon, p_lat = rmc["longitude"], rmc["latitude"]
            if not (-90 <= p_lat <= 90 and -180 <= p_lon <= 180):
                # print("removed for impossible lat/lon: ", rmc)
                continue

            # ignore big jumps
            dt = datetime.datetime.strptime(rmc["date_time"], "%Y-%m-%dT%H:%M:%SZ")
            curr_point = (p_lat, p_lon, dt)
            if prev_point and is_jump(prev_point, curr_point):
                # print("Ignored jump at:", rmc["date_time"])
                # print("removed for big jumps: ", rmc)
                continue

            route_coords.append((rmc["longitude"], rmc["latitude"]))
            all_info.append(rmc)
            prev_point = curr_point

    # TODO: double check this, this is supposed to make it so that we start the 
    # duration count when the car first starts moving and when the car first stops moving
    moving_start, moving_end = get_start_and_end_index(all_info)
    all_info = all_info[moving_start:moving_end+1]
    route_coords = route_coords[moving_start:moving_end+1]

    print("speed at start: ", all_info[0]["speed"])
    print("speed at end: ", all_info[-1]["speed"])

    # print("size of the route_coords: ", len(route_coords))

    # TODO here is where i would put the simplify route function -- issue here is that 
    # decided to not use this bc it messed with the data points too much
    # after filtering out some of the straight points, it no longer follows the curve of the road
    # route_coords = filter_route(route_coords)

    # print("size of the route_coords: ", len(route_coords))

    # split paths if number of points exceed the MAX_POINTS
    for i in range(0, len(route_coords), MAX_POINTS):
        chunk = route_coords[i: i+MAX_POINTS]
        # A. A yellow line along the route of travel - Compl Below 
        line = kml.newlinestring(name="GPS Route")
        line.coords = chunk
        line.extrude = 1 #Task: tell google earth to draw line to ground 

        # B. Do not worry about the altitude. You can set that a 3 meters or something fixed.
        line.altitudemode = simplekml.AltitudeMode.clamptoground #Task: tell gooogle earth how to view

        #A1 - Styling Below 
        line.style.linestyle.width = 3
        line.style.linestyle.color = simplekml.Color.yellow

    # Mark the start and end of the route with green(start) and blue(end)
    # TODO remove this if necessary for submission
    if all_info:
        start = all_info[0]
        end = all_info[-1]
        start_mov = False
        end_mov = False
        missing_s = timedelta(0,0,0,0,0,0,0)
        missing_e = timedelta(0,0,0,0,0,0,0)

        # check to see if the gps file started or stopped while the car is in motion
        if start["speed"] > MOVING:
            print("GPS file started while the car was in motion. The total duration will be an estimate.")
            start_mov = True
        if end["speed"] > MOVING:
            print("GPS file ended while the car was in motion. The total duration will be an estimate.")
            end_mov = True

        start_pt = kml.newpoint(
            name="Start",
            coords=[(start["longitude"], start["latitude"])],
        )
        start_pt.style.iconstyle.color = simplekml.Color.green
        start_pt.style.iconstyle.scale = 1.3
        start_pt.description = f"Start time: {start['date_time']}"

        end_pt = kml.newpoint(
            name="End",
            coords=[(end["longitude"], end["latitude"])],
        )
        end_pt.style.iconstyle.color = simplekml.Color.blue
        end_pt.style.iconstyle.scale = 1.3
        end_pt.description = f"End time: {end['date_time']}"

        if start_mov:
            missing_s = estimate_missing(all_info, 0)
            # print(missing_s)
        if end_mov:
            missing_e = estimate_missing(all_info, -1)
            # print(missing_e)

        # get the trip duration as the first and last gps data 
        start_dt = datetime.datetime.strptime(start["date_time"], "%Y-%m-%dT%H:%M:%SZ")
        end_dt =  datetime.datetime.strptime(end["date_time"], "%Y-%m-%dT%H:%M:%SZ")
        trip_duration = end_dt - start_dt + missing_e + missing_s
        print("Trip started at: ", start_dt)
        print("Trip ended at: ", end_dt)
        print("Total driving time: ", trip_duration)

    # variable to hold last marker location 
    last_marker = None
    # D. A yellow marker if the car made a left turn.
    for i in range(len(route_coords )-2):
        p1 = (route_coords [i][1],route_coords [i][0])  # lat, lon
        p2 = (route_coords [i+1][1], route_coords [i+1][0])
        p3 = (route_coords [i+2][1], route_coords [i+2][0])
        
        direction = turn_direction(p1, p2, p3)
        
        if direction == "left":
            lon, lat= route_coords [i+1]
            # only add a new left turn marker if the distance between the new marker and the prev marker is greater than 5 meters
            if not last_marker or haversine_m(lat, lon, last_marker[0], last_marker[1]) > 10:
                last_marker = (lat, lon)
                point = kml.newpoint(name="Left Turn", coords=[(lon, lat)])
                point.style.iconstyle.color = simplekml.Color.yellow
                point.altitudemode = simplekml.AltitudeMode.clamptoground

    
    # C. A red marker if the car stopped for a stop sign or traffic light.
        # C. A red marker if the car stopped for a stop sign or traffic light.
    current_stop = []


    for point in all_info:
        if point["speed"] < STOP_SPEED:  # speed is at index 2
            current_stop.append(point)
        else:
            if current_stop:
                start_time = current_stop[0]["time"]
                end_time = current_stop[-1]["time"]
                
                
                duration = (end_time - start_time)
                
                if duration >= MIN_STOP:
                    mid_point = current_stop[len(current_stop)//2]
                    
                    stop_marker = kml.newpoint(
                        name="Stop",
                        coords=[(mid_point["longitude"], mid_point["latitude"])]
                    )
                    stop_marker.style.iconstyle.color = simplekml.Color.red
                    stop_marker.style.iconstyle.scale = 1.2
                
                current_stop = []

   
    # print("file complete")
    kml.save(f"gps_data_from_kml.kml")



def main():
    """
    Main

    """
    if len(sys.argv) > 1:
        data = readFile(sys.argv[1])
        makeKMLFile(data[0])
    else:
        print("Missing the gps file. Try again.")


    # data = readFile()
    # data = readFile("Some_Example_GPS_Files/2025_05_01__145019_gps_file.txt")       # home to rit
    # data = readFile("Some_Example_GPS_Files/2025_05_06__021707_gps_file.txt")           # started while in motion, rit to home
    # data = readFile("Some_Example_GPS_Files/2025_05_06__134918_gps_file.txt")           # home to rit w funky jumps (taken care of)
    # data = readFile("Some_Example_GPS_Files/2025_05_06__174741_gps_file.txt")               # starts in motion and ends in motion -- goes from rit to wegmans and back to rit
    # data = readFile("Some_Example_GPS_Files/2025_05_06__211533_gps_file.txt")               # rit to house, no issues 
    # data = readFile("Some_Example_GPS_Files/2025_08_27__144259_gps_file.txt")               # rit to house, no issues
    # data = readFile("Some_Example_GPS_Files/2025_08_27__171823_gps_file.txt")                   # house to rit, no issues
    # data = readFile("Some_Example_GPS_Files/2025_08_27__225846_gps_file.txt")                   # rit to house, no issues
    # data = readFile("Some_Example_GPS_Files/2025_09_02__134904_gps_file.txt")                   # home to rit, no issues
    # data = readFile("Some_Example_GPS_Files/2025_09_05__160041_gps_file.txt")                   # home to rit, marked as started while in motion but speed was marked as like 2mph
    # data = readFile("Some_Example_GPS_Files/2025_09_07__195700_gps_file.txt")                   # went from middle of a road, maybe a stop? to wild wings parking lot...no recorded issues
    # data = readFile("Some_Example_GPS_Files/2025_09_08__223135_gps_file.txt")                   # rit to some lot(?) says ended while car in motion but like its super close to parking, 1.85 knots was the speed, might just up the moving threshold
    # data = readFile("Some_Example_GPS_Files/2025_09_08__Home_to_RIT.txt")                           # home to rit, started at 2.16 knots, ended at 12.1 knots
    # data = readFile("Some_Example_GPS_Files/2025_09_10__172025_gps_file.txt")                       # house to rit, file started in motion
    # data = readFile("Some_Example_GPS_Files/2025_09_10__230616_gps_file.txt")                       # rit to house, recorded car in motion at end w 3.08 knots...might just adjust the threshold
    # data = readFile("Some_Example_GPS_Files/2025_09_11__221355_gps_file.txt")                       # rit to house, no issues
    


if __name__ == "__main__":
    main()
    