#Names: Vivian Hernandez & Jenny Zheng

import datetime
import re
import math
import simplekml
from pathlib import Path
from datetime import timezone

######### STEP 1: Read File #########
def readFile():
    folder_path = Path("Some_Example_GPS_Files/") 
    gps_data = []  # []format 

    for file_path in folder_path.iterdir():

        if file_path.is_file() and file_path.name.startswith("2025_"):#Every file starts with 2025
            try:
                with open(file_path, 'r', encoding='latin1') as f:
                    lines = f.read().splitlines()  
                    temp_arr = []
                    for line in lines[5:]: #Skip teh first 5 lines 
                        if not line.strip():
                            continue
                        parts = line.split(',') #Splits the data by comma
                        parts = [p if p != '' else '0' for p in parts] #makes this an array for the line 
                        temp_arr.append(parts)
                    gps_data.append(temp_arr)
            except Exception as e:
                print(f"Error reading {file_path.name}: {e}")

    
    # print(gps_data[0]) #EXAMPLE
    return gps_data

######### STEP 2: CONVERT DATA TO KML FILE #########


####  HELPER FUNCT ####

def safe_float(value):
    cleaned = re.sub(r"[^0-9.]", "", value)
    return float(cleaned) if cleaned else 0.0

def clean_nmea_field(gps):
    """Remove any non-digit characters from a NMEA field."""
    return ''.join(ch for ch in gps if ch.isdigit())


def nmea_to_decimal(value, direction):
    """
    Converts NMEA ddmm.mmmm to decimal degrees
    Example: 4308.4726, 'N' → 43.141210

    Note: value has to be in str formay 
          NMEA format is fixed -> (d)ddmm.mmmm.
    """
    if '.' in value:
        #
        dec_pos = value.find('.')
        min_start = dec_pos - 2
        degrees_part = safe_float(value[:min_start])
        min_part = float(value[min_start:])

        dec_degrees = degrees_part + (min_part / 60.0)
    else:
        return None #Case: No . found
   
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
    Converts 
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
    """
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dlon)
    
    brng = math.atan2(x, y)
    brng = math.degrees(brng)

    return (brng + 360) % 360

def turn_direction(p1, p2, p3):
    b1 = degree_turn(p1, p2)
    b2 =degree_turn(p2, p3)
    diff = (b2 - b1 + 360) % 360

    if diff > 10 and diff < 180:
        return "left"
    elif diff > 180 and diff < 350:
        return "right"
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



#### MAIN FILE #####
def makeKMLFile(gps_data,num):
    """
    
    array of arrays
    """
    kml = simplekml.Kml()
 
    #Read in the gps info 
    route_coords = []
    all_info =[]
    for arr in gps_data:

        if arr[0].endswith("GPRMC"):
            rmc = read_gprmc(arr) 

            if rmc is None:
                continue 
            route_coords.append((rmc["longitude"], rmc["latitude"]))
            all_info.append(rmc)


    # A. A yellow line along the route of travel - Compl Below 
    line = kml.newlinestring(name="GPS Route")
    line.coords = route_coords
    line.extrude = 1 #Task: tell google earch to draw line to ground 

    # B. Do not worry about the altitude. You can set that a 3 meters or something fixed.
    line.altitudemode = simplekml.AltitudeMode.clamptoground #Task: tell gooogle earth how to view

    #A1 - Styling Below 
    line.style.linestyle.width = 3
    line.style.linestyle.color = simplekml.Color.yellow



    # D. A yellow marker if the car made a left turn.
    for i in range(len(route_coords )-2):
        p1 = (route_coords [i][1],route_coords [i][0])  # lat, lon
        p2 = (route_coords [i+1][1], route_coords [i+1][0])
        p3 = (route_coords [i+2][1], route_coords [i+2][0])
        
        direction = turn_direction(p1, p2, p3)
        
        if direction == "left":
            lon, lat= route_coords [i+1]
            point = kml.newpoint(name="Left Turn", coords=[(lon, lat)])
            point.style.iconstyle.color = simplekml.Color.yellow
    
    # C. A red marker if the car stopped for a stop sign or traffic light.
        # C. A red marker if the car stopped for a stop sign or traffic light.
    STOP_SPEED = 1.0
    MIN_STOP = 1.0
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

   
    print("file complete")
    kml.save(f"gps_data_{num}.kml")##WHEN COMPL UNCOMMENT 



def main():
    """
    Main

    """
    data = readFile()
    num = 1
    
    for arr in data: 
        makeKMLFile(arr,num)
        num = num +1
    



if __name__ == "__main__":
    main()
