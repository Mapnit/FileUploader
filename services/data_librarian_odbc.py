import os, datetime, re, logging, random
import csv, json, requests
import xml.etree.cElementTree as Et
import unittest

# app deployment config
DEPLOY_ROOT = r"C:\ProjectStore\Chen\UploadFile"

# app runtime config
CONFIG_FILE = os.path.join(DEPLOY_ROOT, "UploadFile_odbc.config")

FILE_PATH_SEP = ';'
# limited by the constraints in Esri File-GDB
NAME_MAX_LENGTH = 23

ARCHIVE_FOLDER = 'archive'
ARCHIVE_FILE_EXTENSION = '.arv'

FILE_TYPES = [".csv", '.zip', '.kml', '.kmz', '.gpx']

KML_SHP_TYPES = ['Points', 'Polylines', 'Polygons']

CSV_HEADER_KEYWORDS = {
    "address": ["address"],
    "city": ["city"],
    "state": ["state"],
    "zipcode": ["zip", "zip code", "postal code"],
    "country": ["country"],
    "datum": ["datum"],
    "latitude": ["latitude", "lat"],
    "longitude": ["longitude", "lon", "long"]
}

COORDSYS_LIST = {"WGS84": 4326, "NAD83": 4269, "NAD27": 4267}
TRANSFORMATION_LIST = {"NAD27_to_NAD83": "NAD_1927_To_NAD_1983_NADCON",
                       "NAD83_to_WGS84": "WGS_1984_(ITRF00)_To_NAD_1983"}

BING_GC_URL = "http://dev.virtualearth.net/REST/v1/Locations?key={BING_MAP_KEY}&q={ADDRESS}"
ESRI_GC_URL = "http://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?\
token={ESRI_AGOL_KEY}&address={ADDRESS}&city={CITY}&region={STATE}&postal={ZIPCODE}&countryCode={COUNTRY}&f=json"

# config the logging
##logging.basicConfig(filename=os.path.join(os.path.join(DEPLOY_ROOT, "logs"), "data_librarian.log"),
##                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
##                    level=logging.DEBUG)
from logging.handlers import RotatingFileHandler

log_formatter = logging.Formatter('%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s')
log_handler = RotatingFileHandler(os.path.join(os.path.join(DEPLOY_ROOT, "logs"), "data_librarian.log"),
                                mode='a', maxBytes=5*1024*1024,
                                backupCount=2, encoding=None, delay=0)
log_handler.setFormatter(log_formatter)
log_handler.setLevel(logging.DEBUG)

app_log = logging.getLogger('root')
app_log.setLevel(logging.DEBUG)
app_log.addHandler(log_handler)

# global config variable
config = {}

# load env variables in the config file
def _init_app(config_file):
    app_log.debug("init config file: %s" % config_file)
    xml_file = None
    try:
        xml_file = Et.parse(config_file)
        xml_root = xml_file.getroot()
        for kv_pair in xml_root.findall("./appSettings/add"):
            k = kv_pair.get('key')
            v = kv_pair.get('value')
            config[k] = v
    except Et.ParseError, e:
        print '{"error": "config parse error. %s", "scope":"env"}' % e
    except os.error, e:
        print '{"error": "config file not found. %s", "scope":"env"}' % e
    finally:
        del xml_file
    return


#
# inspect a csv file for addr/loc-related headers
#
def _parse_csv_header(csv_headers):
    idx = 0
    address_fields = {}
    for hdr in csv_headers:
        hdr = hdr.strip().lower()
        # datum field
        if hdr in CSV_HEADER_KEYWORDS["datum"]:
            address_fields["datum"] = {"name": hdr, "index": idx}
        # address fields
        elif hdr in CSV_HEADER_KEYWORDS["address"]:
            address_fields["address"] = {"name": hdr, "index": idx}
        elif hdr in CSV_HEADER_KEYWORDS["city"]:
            address_fields["city"] = {"name": hdr, "index": idx}
        elif hdr in CSV_HEADER_KEYWORDS["state"]:
            address_fields["state"] = {"name": hdr, "index": idx}
        elif hdr in CSV_HEADER_KEYWORDS["zipcode"]:
            address_fields["zipcode"] = {"name": hdr, "index": idx}
        elif hdr in CSV_HEADER_KEYWORDS["country"]:
            address_fields["country"] = {"name": hdr, "index": idx}
        # coordinate fields
        elif hdr in CSV_HEADER_KEYWORDS["latitude"]:
            address_fields["latitude"] = {"name": hdr, "index": idx}
        elif hdr in CSV_HEADER_KEYWORDS["longitude"]:
            address_fields["longitude"] = {"name": hdr, "index": idx}
        idx += 1

    return address_fields


#
# extract address from a row in the csv file
#
def _parse_address(address_fields, data_columns):
    addr_parts = {"address": "", "city": "", "state": "", "zipcode": "", "country": ""}
    # address field
    if "address" in address_fields.keys():
        address = data_columns[address_fields["address"]["index"]]
        addr_parts["address"] = str(address)
    # app_log.debug("address = " + str(address))
    # city field
    if "city" in address_fields.keys():
        city = data_columns[address_fields["city"]["index"]]
        addr_parts["city"] = str(city)
    # app_log.debug("city = " + str(city))
    # state field
    if "state" in address_fields.keys():
        state = data_columns[address_fields["state"]["index"]]
        addr_parts["state"] = str(state)
    # app_log.debug("state = " + str(state))
    # zip field
    if "zipcode" in address_fields.keys():
        zipcode = data_columns[address_fields["zipcode"]["index"]]
        addr_parts["zipcode"] = str(zipcode)
    # app_log.debug("zipcode = " + str(zipcode))
    # country field
    if "country" in address_fields.keys():
        country = data_columns[address_fields["country"]["index"]]
        addr_parts["country"] = str(country)
    # app_log.debug("country = " + str(country))

##    app_log.debug("address line: " + ",".join(addr_part_array))
##    return ",".join(addr_part_array)
    return addr_parts


def geocode_address(addr_parts):
    if config['gc_provider'] == "bing":
        return _geocoder_by_bing(",".join([addr_parts["address"], addr_parts["city"],
            addr_parts["state"], addr_parts["zipcode"], addr_parts["country"]]))
    elif config['gc_provider'] == "esri":
        return _geocoder_by_esri(addr_parts["address"], addr_parts["city"],
            addr_parts["state"], addr_parts["zipcode"], addr_parts["country"])
    else:
        raise Exception("no geocoding provider specified")

#
# extract the geocoded location from the esri response
#
def _geocoder_by_esri(address, city, state, zipcode, country):
    coords = None
    # request Bing to geocode the address
    gc_request_url = ESRI_GC_URL.replace("{ESRI_AGOL_KEY}", config['esri_agol_key'])\
        .replace("{ADDRESS}", address)\
        .replace("{CITY}", "" if len(city)==0 else city)\
        .replace("{STATE}", "" if len(state)==0 else state)\
        .replace("{ZIPCODE}", "" if len(zipcode)==0 else zipcode)\
        .replace("{COUNTRY}", "USA" if len(country)==0 else country)
    req = requests.get(gc_request_url)
    if req.status_code == 200:
        result = req.json()
        if len(result["candidates"]) > 0:
            # match code
            match_code = result["candidates"][0]["score"]
            # take the first one (latitude, longitude)
            coords = [result["candidates"][0]["location"]["y"], result["candidates"][0]["location"]["x"]]
            app_log.debug("%s%% match on the given address [%s]" % (match_code, ",".join([address, city, state, zipcode, country])))
        else:
            app_log.error("no coordinates matching the given address [%s]" % ",".join([address, city, state, zipcode, country]))
    else:
        app_log.error("Esri fails to return the geocoding result {status code: %i]" % req.status_code)

    return coords


#
# extract the geocoded location from the Bing response
#
def _geocoder_by_bing(address_line):
    coords = None
    # request Bing to geocode the address
    gc_request_url = BING_GC_URL.replace("{BING_MAP_KEY}", config['bing_map_key']).replace("{ADDRESS}", address_line)
    req = requests.get(gc_request_url)
    if req.status_code == 200:
        result = req.json()
        count = result["resourceSets"][0]["estimatedTotal"]
        if count > 0:
            # match code
            match_code = result["resourceSets"][0]["resources"][0]["matchCodes"][0]
            # take the first one
            coords = result["resourceSets"][0]["resources"][0]["point"]["coordinates"]
            # gc_result["resourceSets"][0]["resources"][0]["geocodePoints"][0]["coordinates"]
            app_log.debug("%s%% match on the given address [%s]" % (match_code, address_line))
        else:
            app_log.error("no coordinates matching the given address [%s]" % address_line)
    else:
        app_log.error("Bing fails to return the geocoding result {status code: %i]" % req.status_code)

    return coords


#
# list all users shared on a given file with a given user
# - require pyodbc
#
def _list_shared_users_odbc(username, filename, data_filter=None):
    if 'db_conn_string' not in config.keys():
        return None
    if 'shared_user_list' not in config.keys():
        return None

    try:
        import pyodbc as odbc
        db_conn = None
        row_cur = None

        count = 0
        print '['
        try:
            app_log.debug("list all shared users on [%s] [%s]" % (username, filename))
            db_conn = odbc.connect(config['db_conn_string'])
            row_cur = db_conn.cursor()
            row_cur.execute(config['shared_user_list'], (username, filename))
            for row in row_cur:
                shared_user = row[0]
                shared_date = row[1]

                if count > 0:
                    print ','
                print '''{"shared_user":"%s", "shared_date":"%s"}''' \
                      % (shared_user, shared_date)
                count += 1
        except odbc.DatabaseError as e:
            app_log.error('error in list_shared_users: ' + str(e))
            return None
        finally:
            print ']'
            row = None
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        app_log.error('error in list_shared_users: ' + str(e))
        return None


def list_shared_users(username, filename, data_filter=None):
    if config["db_provider"] == "odbc":
        return _list_shared_users_odbc(username, filename, data_filter)
    else:  # default
        return _list_shared_users_lite(username, filename, data_filter)


#
# list all data files shared to a given user
# - require pyodbc
#
def _list_shared_data_odbc(username, data_filter=None):
    if 'db_conn_string' not in config.keys():
        return None
    if 'shared_data_list' not in config.keys():
        return None

    try:
        import pyodbc as odbc
        db_conn = None
        row_cur = None

        count = 0
        print '['
        try:
            app_log.debug("list all data files shared to " + username)
            db_conn = odbc.connect(config['db_conn_string'])
            row_cur = db_conn.cursor()
            row_cur.execute(config['shared_data_list'], (username))
            for row in row_cur:
                owner = row[0]
                src_file_path = row[1]
                data_name = row[2]
                data_size = row[3]
                last_modified = row[4]
                last_uploaded = row[5]
                upload_status = row[6]
                total_row_count = 0 if row[7] is None else row[7]
                cached_row_count = 0 if row[8] is None else row[8]
                drawing_info = "null" if (row[9] is None or len(row[9].strip()) == 0) else row[9]
                shared_date = row[10]

                if count > 0:
                    print ','
                print '''{"owner":"%s", "src_file_path":"%s", "data_name":"%s", "size":%s, "last_modified":"%s", "last_uploaded":"%s",
                        "upload_status":"%s", "total_row_count":%s, "cached_row_count":%s, "drawing_info":%s, "shared_date":"%s"}''' \
                      % (owner, src_file_path, data_name, data_size, last_modified, last_uploaded,
                         upload_status, total_row_count, cached_row_count, drawing_info, shared_date)
                count += 1
        except odbc.DatabaseError as e:
            app_log.error('error in list_shared_data: ' + str(e))
            return None
        finally:
            print ']'
            row = None
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        app_log.error('error in list_shared_data: ' + str(e))
        return None


def list_shared_data(username, data_filter=None):
    if config["db_provider"] == "odbc":
        return _list_shared_data_odbc(username, data_filter)
    elif config["db_provider"] == "oracle":
        return _list_shared_data_ora(username, data_filter)
    else:  # default
        return _list_shared_data_lite(username, data_filter)


#
# add a share entry into database
# - require pyodbc
#
def _share_data_odbc(username, filename, shared_user):
    if 'db_conn_string' not in config.keys():
        return False
    if 'shared_insert' not in config.keys():
        return False

    try:
        import pyodbc as odbc
        db_conn = None
        row_cur = None
        try:
            db_conn = odbc.connect(config['db_conn_string'])
            row_cur = db_conn.cursor()
            # insert a shared entry
            row_cur.execute(config['shared_insert'], (username, filename, shared_user, datetime.datetime.now()))
            db_conn.commit()
            app_log.info("share [%s] [%s] with [%s] "
                         % (username, filename, shared_user))
            return True
        except odbc.DatabaseError as e:
            app_log.error('error in share_data: ' + str(e))
            return False
        finally:
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        app_log.error('error in share_data: ' + str(e))
        return False


def share_data(username, filename, shared_user):
    if config["db_provider"] == "odbc":
        return _share_data_odbc(username, filename, shared_user)
    else:  # default
        return _share_data_lite(username, filename, shared_user)

#
# delete a share entry from database
# - require sqlite
#
def _revoke_share_odbc(username, filename, shared_user):
    if 'db_conn_string' not in config.keys():
        return False
    if 'shared_delete' not in config.keys():
        return False

    try:
        import pyodbc as odbc
        db_conn = None
        row_cur = None
        try:
            db_conn = odbc.connect(config['db_conn_string'])
            row_cur = db_conn.cursor()
            # insert a shared entry
            row_cur.execute(config['shared_delete'], (username, filename, shared_user))
            db_conn.commit()
            app_log.info("remove share of [%s] [%s] from [%s] "
                         % (username, filename, shared_user))
            return True
        except odbc.DatabaseError as e:
            app_log.error('error in revoke_share: ' + str(e))
            return False
        finally:
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        app_log.error('error in revoke_share: ' + str(e))
        return False


def revoke_share(username, filename, shared_user):
    if config["db_provider"] == "odbc":
        return _revoke_share_odbc(username, filename, shared_user)
    else:  # default
        return _revoke_share_lite(username, filename, shared_user)


#
# delete all share entries on a given file from database
# - require sqlite
#
def _revoke_all_shares_odbc(username, filename):
    if 'db_conn_string' not in config.keys():
        return False
    if 'shared_delete_all' not in config.keys():
        return False

    try:
        import pyodbc as odbc
        db_conn = None
        row_cur = None
        try:
            db_conn = odbc.connect(config['db_conn_string'])
            row_cur = db_conn.cursor()
            # insert a shared entry
            row_cur.execute(config['shared_delete_all'], (username, filename))
            db_conn.commit()
            app_log.info("remove share of [%s] [%s] from all users "
                         % (username, filename))
            return True
        except odbc.DatabaseError as e:
            app_log.error('error in revoke_all_shares: ' + str(e))
            return False
        finally:
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        app_log.error('error in revoke_all_shares: ' + str(e))
        return False


def revoke_all_shares(username, filename):
    if config["db_provider"] == "odbc":
        return _revoke_all_shares_odbc(username, filename)
    else:  # default
        return _revoke_all_shares_lite(username, filename)


def _register_cache_odbc(username, filename, cache_file_path, data_name, status, total_row_count, cached_row_count):

    if 'db_conn_string' not in config.keys():
        return False
    if 'data_delete' not in config.keys():
        return False
    if 'data_insert' not in config.keys():
        return False

    src_file_path = os.path.join(os.path.join(config['store'], username), filename)
    try:
        src_modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(src_file_path))
        src_file_size = os.path.getsize(src_file_path)

        import pyodbc as odbc
        db_conn = None
        row_cur = None
        try:
            db_conn = odbc.connect(config['db_conn_string'])
            row_cur = db_conn.cursor()
            # delete the old one
            row_cur.execute(config['data_delete'], (username, filename))
            # add the new one
            row_cur.execute(config['data_insert'], (username, filename, src_file_size, cache_file_path, data_name,
													src_modified_time, datetime.datetime.now(), datetime.datetime.now(),
                                                    status, total_row_count, cached_row_count))
            db_conn.commit()
            app_log.info("register cache of [%s] [%s]: [%s]" % (username, filename, cache_file_path))
            return True
        except odbc.DatabaseError as e:
            app_log.error('error in register_cache: ' + str(e))
            return False
        except Exception as e:
            app_log.error('error in register_cache: ' + str(e))
            return False
        finally:
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        app_log.error('error in register_cache: ' + str(e))
        return False


def _register_cache(username, filename, cache_file_path, data_name,
                    status='READY', total_row_count=0, cached_row_count=0):
    if config["db_provider"] == "odbc":
        return _register_cache_odbc(username, filename, cache_file_path, data_name,
                                   status, total_row_count, cached_row_count)
    else:  # default
        return _register_cache_lite(username, filename, cache_file_path, data_name,
                                    status, total_row_count, cached_row_count)


#
# get the data status from the cache registry
# - require pyodbc
#
def _get_status_odbc(username, filename):

    if 'db_conn_string' not in config.keys():
        return None
    if 'status_query' not in config.keys():
        return None

    try:
        import pyodbc as odbc
        db_conn = None
        row_cur = None
        row = None
        try:
            db_conn = odbc.connect(config['db_conn_string'])
            row_cur = db_conn.cursor()
            # query the status
            row_cur.execute(config['status_query'], (username, filename))
            row = row_cur.fetchone()
            if row is not None:
                return row[0]
            else:
                app_log.info("no such entry [%s] [%s]" % (username, filename))
                return None
        except odbc.DatabaseError as e:
            app_log.error('error in get_status: ' + str(e))
            return None
        finally:
            row = None
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        app_log.error('error in get_status: ' + str(e))
        return None


def get_status(username, filename):
    if config["db_provider"] == "odbc":
        return _get_status_odbc(username, filename)
    else:  # default
        return _get_status_lite(username, filename)


#
# compare the file stats with the metadata in the database
# and check if the user file has been updated since last delivery
# and get the path of the data cache
# - require pyodbc
#
def _get_cache_odbc(username, filename):

    if 'db_conn_string' not in config.keys():
        return None
    if 'data_query' not in config.keys():
        return None

    src_file_path = os.path.join(os.path.join(config['store'], username), filename)
    try:
        src_modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(src_file_path))
        # src_file_size = os.path.getsize(src_file_path)

        import pyodbc as odbc
        db_conn = None
        row_cur = None
        row = None
        try:
            app_log.debug("check the cache registry: " + config['db_conn_string'])
            db_conn = odbc.connect(config['db_conn_string'])
            row_cur = db_conn.cursor()
            row_cur.execute(config['data_touch'], (datetime.datetime.now(), username, filename))
            db_conn.commit()
            row_cur.execute(config['data_query'], (username, filename))
            row = row_cur.fetchone()  # user_name and file_name are made up as Primary key
            if row is not None:
                # pyodbc driver returns datetime.datetime
                last_modified_date = row[0]
                cache_file_paths_string = str(row[1])
                if last_modified_date is not None and cache_file_paths_string is not None:
                    time_delta = src_modified_time - last_modified_date
                    app_log.debug("the cache expires by %f" % time_delta.total_seconds())
                    if abs(time_delta.total_seconds()) < 1:
                        cache_file_paths = cache_file_paths_string.split(FILE_PATH_SEP)
                        cache_exists = True
                        for file_path in cache_file_paths:
                            cache_exists = cache_exists and os.path.exists(file_path)
                            if not cache_exists:
                                app_log.debug("the cache file not found at " + file_path)
                                break
                        if cache_exists:
                            app_log.info("valid cache of [%s] [%s]: [%s]"
                                         % (username, filename, cache_file_paths_string))
                            return cache_file_paths_string
            return None
        except odbc.DatabaseError as e:
            app_log.error('error in get_cache: ' + str(e))
            return None
        finally:
            row = None
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        app_log.error('error in get_cache: ' + str(e))
        return None


def _get_cache(username, filename):
    if config["db_provider"] == "odbc":
        return _get_cache_odbc(username, filename)
    else:  # default
        return _get_cache_lite(username, filename)


#
# move the source data file into an archive folder
#
def _archive_data_file(username, filename):
    user_folder = os.path.join(config['store'], username)
    src_file_path = os.path.join(user_folder, filename)

    if not os.path.exists(src_file_path):
        app_log.error('no such data file [%s]' % filename)
        return None

    else:
        archive_folder_path = os.path.join(user_folder, ARCHIVE_FOLDER)
        if not os.path.exists(archive_folder_path):
            os.mkdir(archive_folder_path)

        archive_ts = datetime.datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
        archive_file_path = os.path.join(archive_folder_path, filename + "(" + archive_ts + ")" + ARCHIVE_FILE_EXTENSION)

        try:
            os.rename(src_file_path, archive_file_path)
        except:
            app_log.error('failed to rename data file [%s]' % filename)
            archive_file_path = None

        return archive_file_path


#
# archive a data file, including its cache registry
#
def _archive_data_odbc(username, filename, archive_file_path, retain_style=False):

    if 'db_conn_string' not in config.keys():
        return False
    if 'data_archive' not in config.keys():
        return False
    if 'data_delete' not in config.keys():
        return False
    if retain_style is True and 'style_delete' not in config.keys():
        return False

    try:
        import pyodbc as odbc
        db_conn = None
        row_cur = None
        try:
            db_conn = odbc.connect(config['db_conn_string'])
            row_cur = db_conn.cursor()
            if archive_file_path is None:
                app_log.warn("delete the orphan registry (source file is missing)")
            else:
                # move the registry to the archived table
                row_cur.execute(config['data_archive'], (archive_file_path, datetime.datetime.now(),
                                                         username, filename))
            # delete the data registry
            row_cur.execute(config['data_delete'], (username, filename))
            # delete the associated style record
            if retain_style is False:
                row_cur.execute(config['style_delete'], (username, filename))
            db_conn.commit()
            app_log.info("archived [%s] [%s] into [%s] (style %s deleted)"
                         % (username, filename, archive_file_path, ("not" if retain_style is True else "is")))
            return True
        except odbc.DatabaseError as e:
            app_log.error('error in archive_data: ' + str(e))
            return False
        finally:
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        app_log.error('error in archive_data: ' + str(e))
        return False


def archive_data(username, filename, retain_style=False):
    archive_file_path = _archive_data_file(username, filename)

    if config["db_provider"] == "odbc":
        return _archive_data_odbc(username, filename, archive_file_path, retain_style)
    else:  # default
        return _archive_data_lite(username, filename, archive_file_path, retain_style)


#
# update the user-defined name (data_name)
#
def _rename_data_odbc(username, filename, new_data_name):
    if 'db_conn_string' not in config.keys():
        return False
    if 'data_rename' not in config.keys():
        return False

    try:
        import pyodbc as odbc
        db_conn = None
        row_cur = None
        try:
            db_conn = odbc.connect(config['db_conn_string'])
            row_cur = db_conn.cursor()
            # update the existing one
            row_cur.execute(config['data_rename'], (new_data_name, username, filename))
            db_conn.commit()
            app_log.info("rename [%s] [%s] to [%s]" % (username, filename, new_data_name))
            return True
        except odbc.DatabaseError as e:
            app_log.error('error in rename_data: ' + str(e))
            return False
        finally:
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        app_log.error('error in rename_data: ' + str(e))
        return False


def rename_data(username, filename, new_data_name):
    if new_data_name is None or len(new_data_name.strip()) == 0:
        print '{"error": "empty data name", "scope":"request"}'
        return False

    if config["db_provider"] == "odbc":
        return _rename_data_odbc(username, filename, new_data_name)
    else:  # default
        return _rename_data_lite(username, filename, new_data_name)


#
# get the data style (drawing_info)
# return drawing_info
#
def _get_style_odbc(username, filename):
    if 'db_conn_string' not in config.keys():
        return False
    if 'style_query' not in config.keys():
        return False

    try:
        import pyodbc as odbc
        db_conn = None
        row_cur = None
        row = None
        drawing_info = None
        try:
            db_conn = odbc.connect(config['db_conn_string'])
            row_cur = db_conn.cursor()
            # check if there is already one
            row_cur.execute(config['style_query'], (username, filename))
            row = row_cur.fetchone()  # user_name and file_name are made up as Primary key
            if row is not None:
                drawing_info = row[0]
            app_log.info("get the style of [%s] [%s]: [%s]" % (username, filename, drawing_info))
            return drawing_info
        except odbc.DatabaseError as e:
            app_log.error('error in get_style: ' + str(e))
            return drawing_info
        finally:
            row = None
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        app_log.error('error in get_style: ' + str(e))
        return False


def get_style(username, filename):
    if config["db_provider"] == "odbc":
        return _get_style_odbc(username, filename)
    else:  # default
        return _get_style_lite(username, filename)


def _set_style_odbc(username, filename, drawing_info):
    if 'db_conn_string' not in config.keys():
        return False
    if 'style_query' not in config.keys():
        return False
    if 'style_insert' not in config.keys():
        return False
    if 'style_update' not in config.keys():
        return False

    try:
        import pyodbc as odbc
        db_conn = None
        row_cur = None
        row = None
        try:
            db_conn = odbc.connect(config['db_conn_string'])
            row_cur = db_conn.cursor()
            # check if there is already one
            row_cur.execute(config['style_query'], (username, filename))
            row = row_cur.fetchone()  # user_name and file_name are made up as Primary key
            if row is not None:
                # update the existing one
                row_cur.execute(config['style_update'], (drawing_info, username, filename))
            else:
                # insert a new one
                row_cur.execute(config['style_insert'], (username, filename, drawing_info))
            # commit changes
            db_conn.commit()

            app_log.info("set the style of [%s] [%s]: [%s]" % (username, filename, drawing_info))
            return True
        except odbc.DatabaseError as e:
            app_log.error('error in set_style: ' + str(e))
            return False
        finally:
            row = None
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        app_log.error('error in set_style: ' + str(e))
        return False


def set_style(username, filename, drawing_info):
    if config["db_provider"] == "odbc":
        return _set_style_odbc(username, filename, drawing_info)
    else:  # default
        return _set_style_lite(username, filename, drawing_info)


#
# create a default symbol in json
#
def _get_default_style(geom_type, label=None, description=None):

    label = "" if label is None else label
    description = "" if description is None else description
    geom_type = geom_type.lower()

    if geom_type.find("point") > -1:
        style_file_path = config["default_style_point"]
    elif geom_type.find("line") > -1:
        style_file_path = config["default_style_line"]
    elif geom_type.find("polygon") > -1:
        style_file_path = config["default_style_polygon"]
    else:
        return None

    # read out the file content
    with open(style_file_path, "r") as json_file:
        style_json = json_file.read()

    # create the renderer
    return '{"type": "simple", "label": "%s", "description": "%s", %s}' % (label, description, style_json)


#
# normalize a filename by removing any illegal char
#
def _normalize_name(name):
    # (2016/2/5) added alpha prefix to eliminate illegal layer name
	# (2016/2/12) shortened the prefix, which had made some names too long and caused "arcpy.Statistics_analysis" to throw an error of invalid table name
    return 'n_' + '_'.join(re.split('[\W]+', name))


def _write_features_json(datapath, json_file_path):
    import arcpy
    from arcpy import env

    env.overwriteOutput = True
    app_log.info("output features to json [%s]" % json_file_path)
    arcpy.FeaturesToJSON_conversion(datapath, json_file_path)  # , "FORMATTED"

#
# output features in json
# (2019/3/29) changed the output from array to featureCollection
#
def _output_feature_json(json_file_path, output_name=None):
    app_log.info("serve json from the cache file [%s]" % json_file_path)
    print '{"featureCollection": '
    with open(json_file_path, "r") as json_file:
        for txtline in json_file:
            print txtline
    print "}"


#
# TODO: support the featurecollection format
#
def _convert_to_featurecoll(stg_json_paths, carto_styles_array, data_despt_array, data_name, cache_json_path):
    app_log.debug("carto_styles_array: %s" % carto_styles_array)
    count = 0
    # featureCollection
    featureColl = {"showLegend": "true", "layers": []}
    # convert each file
    for file_path in stg_json_paths:
        app_log.info("load json from the cache file [%s]" % file_path)
        # compose the featurecoll object
        with open(file_path, "r") as json_file:
            stagedData = json.load(json_file)
            layerObj = {"featureSet": {
                "spatialReference": stagedData["spatialReference"],
                "geometryType": stagedData["geometryType"],
                "features": stagedData["features"]
            }, "layerDefinition": {
                "currentVersion": "10.61",
                "id": count,
                "dislayField": stagedData["displayFieldName"],
                "objectIdField": data_despt_array[count].OIDFieldName,
                "hasM": data_despt_array[count].hasM,
                "hasZ": data_despt_array[count].hasZ,
                "isDataVersioned": data_despt_array[count].isVersioned,
                "fields": stagedData["fields"],
                "geometryType": stagedData["geometryType"],
                "extent": json.loads(data_despt_array[count].extent.JSON),
                "name": data_name,
                "type": "Feature Layer",
                "drawingInfo": {"renderer": json.loads(carto_styles_array[count])},
                "htmlPopupType": "esriServerHTMLPopupTypeNone",
                "defaultVisibility": "true",
                "capabilities": "Query",
                "supportedQueryFormat": "JSON"
            }}
            featureColl["layers"].append(layerObj)
        count += 1
    # write featurecollection into a file
    with open(cache_json_path, "w") as outfile:
        json.dump(featureColl, outfile)


# create a layer of features fewer than the defined max number of rows
# return the filtered layer, total row count, filtered row count
#
def _filter_data_by_count(file_path, oid_column, stg_workspace, extra_name=""):

    import arcpy
    from arcpy import env

    env.overwriteOutput = True

    fname, fext = os.path.splitext(os.path.basename(file_path))
    # (2016/2/4) remove any illegal char in file base name
    fname = _normalize_name(fname[0:NAME_MAX_LENGTH])
    #
    extra_name = "" if extra_name is None else extra_name.strip()

    stats_fields = [[oid_column, "MIN"]]
    stats_table = os.path.join(stg_workspace, "%s_%s_stats" % (fname, extra_name))
    filtered_layer_name = "%s_%s_filtered_layer" % (fname, extra_name)
    # filtered_file_path = os.path.join(stg_workspace, "%s_%s_filtered%s" % (fname, extra_name, fext))

    app_log.info("calculate the feature count")
    arcpy.Statistics_analysis(file_path, stats_table, stats_fields)

    max_count = int(config["max_num_of_rows"])
    cnt_oid = 0
    min_oid = 0

    with arcpy.da.SearchCursor(stats_table, ["FREQUENCY", "MIN_" + oid_column]) as cursor:
        for row in cursor:
            cnt_oid = row[0]
            min_oid = row[1]
            break

    if cnt_oid > max_count:
        app_log.info("limit the number of features (%i) to %i" % (cnt_oid, max_count))
        where_clause = "%s < %i" % (oid_column, min_oid + max_count)
        arcpy.MakeFeatureLayer_management(file_path, filtered_layer_name, where_clause)
        # arcpy.CopyFeatures_management(filtered_layer_name, filtered_file_path)
        # return filtered_file_path
        return filtered_layer_name, cnt_oid, max_count
    else:
        app_log.info("no limit since the number of features (%i) is less than %i" % (cnt_oid, max_count))
        return file_path, cnt_oid, cnt_oid

#
# read a file and convert its data into a json format
# return the json file path, the drawing style, total row count, cached row count
# - require arcpy
# TODO - refactor code
#
def _prepare_data(username, filename):
    src_file_path = os.path.join(os.path.join(config['store'], username), filename)
    if not os.path.exists(src_file_path):
        print '{"error": "no such data file [%s]", "scope":"env"}' % filename
        return None, None, 0, 0

    # create intermediate folders
    stage_user_folder = os.path.join(config['stage'], username)
    if not os.path.exists(stage_user_folder):
        os.mkdir(stage_user_folder)

    cache_user_folder = os.path.join(config['cache'], username)
    if not os.path.exists(cache_user_folder):
        os.mkdir(cache_user_folder)

    rand_number = str(random.random()).split('.')[-1]

    stg_folder = os.path.join(stage_user_folder, rand_number)
    if not os.path.exists(stg_folder):
        os.mkdir(stg_folder)

    cache_folder = os.path.join(cache_user_folder, rand_number)
    if not os.path.exists(cache_folder):
        os.mkdir(cache_folder)

    fname, fext = os.path.splitext(os.path.basename(filename))
    fname_norm = _normalize_name(fname)
    fext = fext.lower()

    stg_fgdb_name = username + ".gdb"
    stg_fgdb_path = os.path.join(stg_folder, stg_fgdb_name)
    # stg_fgdb_path = "in_memory"

    import arcpy
    from arcpy import env

    env.overwriteOutput = True
    output_spatial_ref = arcpy.SpatialReference(int(config["output_wkid"]))

    stg_json_path_string = None
    stg_json_paths = []

    total_row_count = 0
    filtered_row_count = 0

    carto_styles_string = get_style(username, filename)
    carto_styles_array = []
    if carto_styles_string is not None and len(carto_styles_string) > 0:
        carto_styles_array = json.loads(carto_styles_string)

    data_despt_array = []

    if fext == ".zip":  # zipped shapefile
        # unzip the zip file
        app_log.info("unzip file [%s] to [%s]" % (src_file_path, stg_folder))
        import zipfile
        with zipfile.ZipFile(src_file_path, "r") as zipShpFile:
            zipShpFile.extractall(stg_folder)
            namelist = zipShpFile.namelist()
            # {2016/2/4) search for shape file and ignore others
            shp_filename = None
            for sfn in namelist:
                if sfn[-4:].lower() == ".shp":
                    # only take the first shapefile
                    shp_filename = sfn
                    break

        if shp_filename is None:
            app_log.error("no shape file found in [%s]" % src_file_path)
        else:
            unzip_base, unzip_ext = os.path.splitext(shp_filename)
            unzip_dir = os.path.dirname(unzip_base)
            unzip_base = os.path.basename(unzip_base)
            stg_data_path = os.path.join(os.path.join(stg_folder, unzip_dir), unzip_base + ".shp")
            app_log.info("unzipped shape file [%s]" % stg_data_path)

        data_despt = arcpy.Describe(stg_data_path)
        # assign default symbology
        if carto_styles_string is None:
            carto_styles_array.append(_get_default_style(data_despt.shapeType))
        # limit data by count
        stg_data_path, total_row_count, filtered_row_count = _filter_data_by_count(
            stg_data_path, data_despt.OIDFieldName, stg_folder)
        # transform or project to the standard spatial ref
        src_spatial_ref = data_despt.spatialReference
        if src_spatial_ref.name != output_spatial_ref.name:
            app_log.debug("Project data from %s(%d) to %s(%d)"
                % (src_spatial_ref.name, src_spatial_ref.factoryCode, output_spatial_ref.name, output_spatial_ref.factoryCode))
            stg_prep_file_path = os.path.join(os.path.join(stg_folder, unzip_dir), unzip_base + "_prep.shp")
            arcpy.Project_management(stg_data_path, stg_prep_file_path, output_spatial_ref)
            stg_data_path = stg_prep_file_path
            data_despt = arcpy.Describe(stg_data_path)
        data_despt_array.append(data_despt)

        # write features to json
        stg_json_path_string = os.path.join(cache_folder, fname + ".json")
        _write_features_json(stg_data_path, stg_json_path_string)
        stg_json_paths.append(stg_json_path_string)

        # cleanup
        # arcpy.Delete_management(stg_data_path)

    elif fext == ".gpx":  # gpx
        if not arcpy.Exists(stg_fgdb_path):
            app_log.info("create fgdb [%s] under [%s]" % (stg_fgdb_name, stg_folder))
            arcpy.CreateFileGDB_management(stg_folder, stg_fgdb_name)

        # convert to feature class
        app_log.info("convert gpx [%s] to staging fgdb in [%s]" % (src_file_path, stg_fgdb_path))
        stg_data_path = os.path.join(stg_fgdb_path, fname_norm)
        arcpy.GPXtoFeatures_conversion(src_file_path, stg_data_path)

        data_despt = arcpy.Describe(stg_data_path)
        # assign default symbology
        if carto_styles_string is None:
            carto_styles_array.append(_get_default_style(data_despt.shapeType))
        # limit data by count
        stg_data_path, total_row_count, filtered_row_count = _filter_data_by_count(
            stg_data_path, data_despt.OIDFieldName, stg_fgdb_path)
        # transform or project to the standard spatial ref
        src_spatial_ref = data_despt.spatialReference
        if src_spatial_ref.name != output_spatial_ref.name:
            app_log.debug("Project data from %s(%d) to %s(%d)"
                % (src_spatial_ref.name, src_spatial_ref.factoryCode, output_spatial_ref.name, output_spatial_ref.factoryCode))
            stg_prep_file_path = stg_data_path + "_prep"
            arcpy.Project_management(stg_data_path, stg_prep_file_path, output_spatial_ref)
            stg_data_path = stg_prep_file_path
            data_despt = arcpy.Describe(stg_data_path)
        data_despt_array.append(data_despt)

        # output features to json
        stg_json_path_string = os.path.join(cache_folder, fname + ".json")
        _write_features_json(stg_data_path, stg_json_path_string)
        stg_json_paths.append(stg_json_path_string)

        # cleanup
        # arcpy.Delete_management(stg_data_path)

    elif fext == ".csv":  # csv
        src_spatial_ref = None
        # extract addr/loc columns from csv
        with open(src_file_path, "rb") as csvf:
            csv_reader = csv.reader(csvf)
            # inspect header line
            csv_headers = csv_reader.next()
            csv_qualifiers = _parse_csv_header(csv_headers)
            # the 1st data line
            data_fields = csv_reader.next()
            # datum field
            if "datum" in csv_qualifiers.keys():
                src_datum = data_fields[csv_qualifiers["datum"]["index"]]
                src_datum = src_datum.upper()
                if src_datum in COORDSYS_LIST.keys():
                    app_log.info("found datum [%s] in csv [%s]" % (src_datum, src_file_path))
                    src_spatial_ref = arcpy.SpatialReference(COORDSYS_LIST[src_datum])
            else:
                app_log.info("found no datum (and assumed WGS84) in csv [%s]" % src_file_path)

        # check the addr/loc columns
        if "latitude" not in csv_qualifiers.keys() or "longitude" not in csv_qualifiers.keys():
            app_log.info("found no latitude or longitude column in csv [%s]" % src_file_path)
            if not ("address" in csv_qualifiers.keys() or "zipcode" in csv_qualifiers.keys()):
                app_log.error("found no address or zipcode column in csv [%s]" % src_file_path)
                # error out because no data can be spatialized
                raise Exception('no column can be transformed to a spatial shape')
            else:
                # geocode each row
                app_log.info("geocode address in csv [%s]" % src_file_path)
                csv_filepath_gc = os.path.join(stg_folder, fname + ".csv")
                with open(csv_filepath_gc, "wb") as csvfw:
                    csv_writer = csv.writer(csvfw)
                    with open(src_file_path, "rb") as csvfr:
                        csv_reader = csv.reader(csvfr)
                        # read the first/header line
                        csv_headers = csv_reader.next()
                        csv_headers.append("latitude")
                        csv_headers.append("longitude")
                        csv_writer.writerow(csv_headers)
                        # read the data rows from the 2nd line
                        for data_fields in csv_reader:
                            address_parts = _parse_address(csv_qualifiers, data_fields)
                            gc_coords = geocode_address(address_parts)
                            if gc_coords is not None:
                                data_fields.append(gc_coords[0])
                                data_fields.append(gc_coords[1])
                                csv_writer.writerow(data_fields)

                src_file_path = csv_filepath_gc
                csv_qualifiers['latitude'] = {'index': len(csv_headers)-2, "name": 'latitude'}
                csv_qualifiers['longitude'] = {'index': len(csv_headers)-1, "name": 'longitude'}

        # make file-gdb as a staging db
        if not arcpy.Exists(stg_fgdb_path):
            app_log.info("create fgdb [%s] under [%s]" % (stg_fgdb_name, stg_folder))
            arcpy.CreateFileGDB_management(stg_folder, stg_fgdb_name)

        # convert to feature class
        app_log.info("convert csv [%s] to staging fgdb in [%s]" % (src_file_path, stg_fgdb_path))
        csv_layer_name = fname_norm + "_csv_layer"
        if src_spatial_ref is None:
            src_spatial_ref = output_spatial_ref

        # accommodate the varieties of the latitude/longitude columns
        #arcpy.MakeXYEventLayer_management(src_file_path, "longitude", "latitude",
        arcpy.MakeXYEventLayer_management(src_file_path, csv_qualifiers['longitude']['name'], csv_qualifiers['latitude']['name'],
                                          csv_layer_name, src_spatial_ref)

        stg_data_path = os.path.join(stg_fgdb_path, fname_norm)
        arcpy.CopyFeatures_management(csv_layer_name, stg_data_path)

        data_despt = arcpy.Describe(stg_data_path)
        # assign default symbology
        if carto_styles_string is None:
            carto_styles_array.append(_get_default_style(data_despt.shapeType))
        # limit data by count
        stg_data_path, total_row_count, filtered_row_count = _filter_data_by_count(
            stg_data_path, data_despt.OIDFieldName, stg_fgdb_path)

        # transform or project to the output spatial ref if necessary
        if data_despt.spatialReference.factoryCode == COORDSYS_LIST["NAD27"]:
            # NAD27 -> NAD83
            app_log.info("project from NAD27 to NAD83 on csv [%s]" % stg_data_path)
            output_spatial_ref = arcpy.SpatialReference(COORDSYS_LIST["NAD83"])
            stg_prep_file_path = stg_data_path + "_prep2"
            arcpy.Project_management(stg_data_path, stg_prep_file_path, output_spatial_ref,
                                     TRANSFORMATION_LIST["NAD27_to_NAD83"])
            stg_data_path = stg_prep_file_path
            data_despt = arcpy.Describe(stg_data_path)

        if data_despt.spatialReference.factoryCode == COORDSYS_LIST["NAD83"]:
            # NAD83 -> WGS84
            app_log.info("project from NAD83 to WGS84 on csv [%s]" % stg_data_path)
            output_spatial_ref = arcpy.SpatialReference(COORDSYS_LIST["WGS84"])
            stg_prep_file_path = stg_data_path + "_prep1"
            arcpy.Project_management(stg_data_path, stg_prep_file_path, output_spatial_ref,
                                     TRANSFORMATION_LIST["NAD83_to_WGS84"])
            stg_data_path = stg_prep_file_path
            data_despt = arcpy.Describe(stg_data_path)

        data_despt_array.append(data_despt)

        # output features to json
        stg_json_path_string = os.path.join(cache_folder, fname + ".json")
        _write_features_json(stg_data_path, stg_json_path_string)
        stg_json_paths.append(stg_json_path_string)

        # cleanup
        # arcpy.Delete_management(stg_data_path)

    elif fext in [".kmz", ".kml"]:  # kml/kmz
        # convert to feature class
        app_log.info("convert kml/kmz [%s] to staging fgdb in [%s]" % (src_file_path, stg_folder))
        arcpy.KMLToLayer_conversion(src_file_path, stg_folder, fname_norm)

        # traverse the datasets
        stg_fgdb_path = os.path.join(stg_folder, fname_norm + ".gdb")
        env.workspace = stg_fgdb_path
        datasets = arcpy.ListDatasets()
        for ds_name in datasets:
            stg_ds_path = os.path.join(stg_fgdb_path, ds_name)
            for shp_type in KML_SHP_TYPES:
                stg_data_path = os.path.join(stg_ds_path, shp_type)

                if arcpy.Exists(stg_data_path):
                    data_despt = arcpy.Describe(stg_data_path)
                    # assign default symbology
                    if carto_styles_string is None:
                        carto_styles_array.append(_get_default_style(data_despt.shapeType, shp_type))
                    # limit data by count
                    stg_data_path, total_count, filtered_count = _filter_data_by_count(
                        stg_data_path, data_despt.OIDFieldName, stg_fgdb_path, shp_type)
                    # transform or project to the standard spatial ref
                    src_spatial_ref = data_despt.spatialReference
                    if src_spatial_ref.name != output_spatial_ref.name:
                        app_log.debug("Project data from %s(%d) to %s(%d)"
                            % (src_spatial_ref.name, src_spatial_ref.factoryCode, output_spatial_ref.name, output_spatial_ref.factoryCode))
                        stg_prep_file_path = stg_data_path + "_prep"
                        arcpy.Project_management(stg_data_path, stg_prep_file_path, output_spatial_ref)
                        stg_data_path = stg_prep_file_path
                        data_despt = arcpy.Describe(stg_data_path)
                    data_despt_array.append(data_despt)

                    # output features to json
                    stg_json_path = os.path.join(cache_folder, "%s_%s_%s.json" % (fname, ds_name, shp_type))
                    _write_features_json(stg_data_path, stg_json_path)
                    # add it to the cache file array
                    stg_json_paths.append(stg_json_path)

                    # add total_row_count, filtered_count
                    total_row_count += total_count
                    filtered_row_count += filtered_count

        stg_json_path_string = FILE_PATH_SEP.join(stg_json_paths)

        # cleanup
        # arcpy.env.workspace = None
        # arcpy.Delete_management(stg_fgdb_path)

    else:
        app_log.error("unsupported file type: %s" % fext)

    carto_styles_string = json.dumps(carto_styles_array)

    # transform json into featureCollection
    cache_json_path = os.path.join(cache_folder, "%s_%s.json" % (fname, "featurecoll"))
    _convert_to_featurecoll(stg_json_paths, carto_styles_array, data_despt_array, fname, cache_json_path)

    #return stg_json_path_string, carto_styles_string, total_row_count, filtered_row_count
    return cache_json_path, carto_styles_string, total_row_count, filtered_row_count


#
# check the cache first.
# If not cached, prepare the data. Otherwise, return the cache
#
def get_data(username, filename):

    fname, fext = os.path.splitext(os.path.basename(filename))

    cache_json_path_string = _get_cache(username, filename)
    if cache_json_path_string is not None:
        app_log.info("use cached data: [%s]" % cache_json_path_string)
    else:
        # merely create a registry entry
        _register_cache(username, filename, u"", fname, u"PROCESSING")
        # prepare data
        app_log.debug("prepare data into json")
        cache_json_path_string, carto_json_string, total_row_count, cached_row_count = _prepare_data(username, filename)
        # register the data with the cache and status info
        if cache_json_path_string is not None:
            _register_cache(username, filename, cache_json_path_string, fname, u"READY", total_row_count, cached_row_count)
        # set the style
        if carto_json_string is not None:
            set_style(username, filename, carto_json_string)

    # output feature as json
    if cache_json_path_string is not None:
        app_log.debug("send out data")
        _output_feature_json(cache_json_path_string)


#
# list all files belonging to a given user with a filter
# (from file system)
#
def _list_files(username, data_filter=None):
    list_folder = os.path.join(config['store'], username)
    app_log.debug('user folder: ' + list_folder)

    try:
        count = 0
        print '['
        for fn in os.listdir(list_folder):
            fp_full = os.path.join(list_folder, fn)
            fn_base, fn_ext = os.path.splitext(fn)
            if fn_ext.lower() in FILE_TYPES and os.path.isfile(fp_full):
                app_log.debug("user file: " + fp_full)
                modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(fp_full))
                file_size = os.path.getsize(fp_full)
                if count > 0:
                    print ','
                print '{"filename":"%s", "last_modified":"%s", "size":%s}' \
                      % (fn, modified_time.strftime("%Y-%m-%d %H:%M:%S"), file_size)
                count += 1
    except os.error, err:
        print '{"error": "failed to list data files", "scope":"env"}'
        app_log.error('error in list_data: ' + str(err))
    finally:
        print ']'


#
# list all data files belonging to a given user
# (from data registry table in database)
#
def _list_data_odbc(username, data_filter=None):
    if 'db_conn_string' not in config.keys():
        return None
    if 'data_list' not in config.keys():
        return None

    try:
        import pyodbc as odbc
        db_conn = None
        row_cur = None

        count = 0
        print '['
        try:
            app_log.debug("list all data files owned by " + username)
            db_conn = odbc.connect(config['db_conn_string'])
            row_cur = db_conn.cursor()
            row_cur.execute(config['data_list'], (username))
            for row in row_cur:
                src_file_path = row[0]
                data_name = row[1]
                data_size = row[2]
                last_modified = row[3]
                last_uploaded = row[4]
                upload_status = row[5]
                total_row_count = 0 if row[6] is None else row[6]
                cached_row_count = 0 if row[7] is None else row[7]
                drawing_info = "null" if (row[8] is None or len(row[8].strip()) == 0) else row[8]

                if count > 0:
                    print ','
                print '{"src_file_path":"%s", "data_name":"%s", "size":%s, "last_modified":"%s", "last_uploaded":"%s", "upload_status":"%s", "total_row_count":%s, "cached_row_count":%s, "drawing_info":%s}' \
                      % (src_file_path, data_name, data_size, last_modified, last_uploaded,
                         upload_status, total_row_count, cached_row_count, drawing_info)
                count += 1
        except odbc.DatabaseError as e:
            app_log.error('error in list_data: ' + str(e))
            return None
        except Exception as e:
            app_log.error('error in list_data: ' + str(e))
            return None
        finally:
            print ']'
            row = None
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        app_log.error('error in list_data: ' + str(e))
        return None


def list_data(username, data_filter=None):
    if config["db_provider"] == "odbc":
        return _list_data_odbc(username, data_filter)
    else:  # default
        return _list_data_lite(username, data_filter)


#
# web response supports four actions:
# - list, list_files, archive, rename, style
#
def response():
    import cgi
    import cgitb; cgitb.enable()  # Optional; for debugging only

    print "Content-Type: application/json"
    print ""

    arguments = cgi.FieldStorage()
    if 'username' not in arguments.keys():
        print '{"error": "unknown user", "scope":"request"}'
    elif 'action' not in arguments.keys():
        print '{"error": "unknown action", "scope":"request"}'
    else:
        app_log.info("request parameters: ")
        for i in arguments.keys():
            app_log.debug(" - " + str(i) + ": " + str(arguments[i].value))

        username = str(arguments['username'].value).lower()
        # app_log.info(" - username: " + username)
        action = str(arguments['action'].value).lower()
        # app_log.info(" - action: " + action)
        filters = None
        if 'filters' in arguments.keys() and arguments['filters'].value is not None:
            filters = str(arguments['filters'])
        app_log.info(" - filters: " + str(filters))

        if action == 'list':
            app_log.info("execute: list files satisfying filters [%s] " % str(filters))
            list_data(username, filters)

        elif action == 'list_files':
            app_log.info("execute: list files satisfying filters [%s] " % str(filters))
            _list_files(username, filters)

        elif action == 'data':
            if 'filename' in arguments.keys() and arguments['filename'].value is not None:
                filename = str(arguments['filename'].value)
                get_data(username, filename)
            else:
                print '{"error": "unknown file name", "scope":"request"}'

        elif action == 'rename':
            if 'filename' in arguments.keys() and arguments['filename'].value is not None:
                filename = str(arguments['filename'].value)
            else:
                print '{"error": "unknown file name", "scope":"request"}'
                return

            if 'data_name' in arguments.keys() and arguments['data_name'].value is not None:
                new_data_name = arguments['data_name'].value
            else:
                print '{"error": "unknown data name", "scope":"request"}'
                return

            if rename_data(username, filename, new_data_name):
                print '{"status": "success", "scope":"response", "filename":"%s"}' % filename

        elif action == 'style':
            if 'filename' in arguments.keys() and arguments['filename'].value is not None:
                filename = str(arguments['filename'].value)
            else:
                print '{"error": "unknown file name", "scope":"request"}'
                return

            drawing_info = None
            if 'drawing_info' in arguments.keys() and arguments['drawing_info'].value is not None:
                drawing_info = arguments['drawing_info'].value

            if set_style(username, filename, drawing_info):
                print '{"status": "success", "scope":"response", "filename":"%s"}' % filename

        elif action == 'archive':
            if 'filename' in arguments.keys() and arguments['filename'].value is not None:
                filename = str(arguments['filename'].value)
            else:
                print '{"error": "unknown file name", "scope":"request"}'
                return

            if archive_data(username, filename):
                print '{"status": "success", "scope":"response", "filename":"%s"}' % filename

        elif action == 'list_shared_data':
            app_log.info("execute: list all shared files satisfying filters [%s] " % str(filters))
            list_shared_data(username, filters)

        elif action == 'list_shared_users':
            if 'filename' in arguments.keys() and arguments['filename'].value is not None:
                filename = str(arguments['filename'].value)
            else:
                print '{"error": "unknown file name", "scope":"request"}'
                return

            if list_shared_users(username, filename):
                print '{"status": "success", "scope":"response", "filename":"%s"}' % filename

        elif action == 'share':
            if 'filename' in arguments.keys() and arguments['filename'].value is not None:
                filename = str(arguments['filename'].value)
            else:
                print '{"error": "unknown file name", "scope":"request"}'
                return

            if 'shared_user' in arguments.keys() and arguments['shared_user'].value is not None:
                shared_user = arguments['shared_user'].value
            else:
                print '{"error": "unknown user to share", "scope":"request"}'
                return

            if share_data(username, filename, shared_user):
                print '{"status": "success", "scope":"response", "filename":"%s"}' % filename

        elif action == "status":
            if 'filename' in arguments.keys() and arguments['filename'].value is not None:
                filename = str(arguments['filename'].value)
            else:
                print '{"error": "unknown file name", "scope":"request"}'
                return

            status = get_status(username, filename)
            print '{"status": "%s", "scope":"response", "filename":"%s"}' % (status, filename)

        else:
            print '{"error": "unknown action", "scope":"request"}'

    app_log.info("response completed")
    return


#
# Test Cases
#
class TestDataLibrarian(unittest.TestCase):

    def setUp(self):
        # need to grab configs again inside TestClass
        _init_app(CONFIG_FILE)

    def test_list_files(self):

        print "***** list_files('imaps') *****"
        _list_files("imaps")
        print "##### list_files('imaps') #####"

    def test_list_data(self):

        print "***** list_data('imaps') *****"
        list_data("imaps")
        print "##### list_data('imaps') #####"

    def test_get_data_imap(self):

        print "***** get_data('imaps', 'High_Schools.csv') *****"
        get_data("imaps", "High_Schools.csv")
        print "##### get_data('imaps', 'High_Schools.csv') #####"

        print "***** get_data('imaps', 'earthquakes!^ last_month.csv') *****"
        get_data("imaps", "earthquakes!^ last_month.csv")
        print "##### get_data('imaps', 'earthquakes!^ last_month.csv') #####"

        print "***** get_data('imaps', 'Earthquakes1970.zip') *****"
        get_data("imaps", "Earthquakes1970.zip")
        print "##### get_data('imaps', 'Earthquakes1970.zip') #####"

        print "***** get_data('imaps', 'Public_School_Locations.zip') *****"
        get_data("imaps", "Public_School_Locations.zip")
        print "##### get_data('imaps', 'Public_School_Locations.zip') #####"

        print "***** get_data('imaps', 'ZipCodes.zip') *****"
        get_data("imaps", "ZipCodes.zip")
        print "##### get_data('imaps', 'ZipCodes.zip') #####"

        print "***** get_data('imaps', 'FuquayVarina_Zoning.zip') *****"
        get_data("imaps", "FuquayVarina_Zoning.zip")
        print "##### get_data('imaps', 'FuquayVarina_Zoning.zip') #####"

        print "***** get_data('imaps', 'Private_Water_Line.zip') *****"
        get_data("imaps", "Private_Water_Line.zip")
        print "##### get_data('imaps', 'Private_Water_Line.zip') #####"

        print "***** get_data('imaps', 'KFC_2019_73_.gpx') *****"
        get_data("imaps", "KFC_2019_73_.gpx")
        print "##### get_data('imaps', 'KFC_2019_73_.gpx') #####"

        print "***** get_data('imaps', 'KML_Samples.kml') *****"
        get_data("imaps", "KML_Samples.kml")
        print "##### get_data('imaps', 'KML_Samples.kml') #####"

        print "***** get_data('imaps', 'Oil_Spill.kmz') *****"
        get_data("imaps", "Oil_Spill.kmz")
        print "##### get_data('imaps', 'Oil_Spill.kmz') #####"

        print "***** get_data('imaps', 'significant earthquakes of last month.csv') *****"
        get_data("imaps", "significant earthquakes of last month.csv")
        print "##### get_data('imaps', 'significant earthquakes of last month.csv') #####"

    def test_get_status(self):

        print "***** get_status('imaps', 'KML_Samples.kml') *****"
        get_status("imaps", "KML_Samples.kml")
        print "##### get_status('imaps', 'KML_Samples.kml') #####"

        print "***** get_status('imaps', 'earthquakes.csv') *****"
        get_status("imaps", "earthquakes.csv")
        print "##### get_status('imaps', 'earthquakes.csv') #####"

    def test_archive_data(self):

        print "***** get_data('imaps', 'KFC_2019_73_.gpx') *****"
        get_data("imaps", "KFC_2019_73_.gpx")
        print "##### get_data('imaps', 'KFC_2019_73_.gpx') #####"

        print "***** archive_data('imaps', 'Oil_Spill.kmz') *****"
        archive_data("imaps", "Oil_Spill.kmz")
        print "##### archive_data('imaps', 'Oil_Spill.kmz') #####"

        print "***** archive_data('imaps', 'high_schools.csv') *****"
        archive_data("imaps", "high_schools.csv")
        print "##### archive_data('imaps', 'high_schools.csv') #####"

        print "***** archive_data('znh623', '2.5_hour.csv') *****"
        archive_data("znh623", "2.5_hour.csv")
        print "##### archive_data('znh623', '2.5_hour.csv') #####"

    def test_rename_data(self):

        print "***** list_data('imaps') *****"
        list_data("imaps")
        print "##### list_data('imaps') #####"

        print "***** rename_data('imaps', 'Public_School_Locations.zip', 'Public Schools') *****"
        rename_data("imaps", "Public_School_Locations.zip", "Public Schools")
        print "##### rename_data('imaps', 'Public_School_Locations.zip', 'Public Schools') #####"

        print "***** list_data('imaps') *****"
        list_data("imaps")
        print "##### list_data('imaps') #####"

    def test_style_data(self):

        print "***** list_data('imaps') *****"
        list_data("imaps")
        print "##### list_data('imaps') #####"

        print "***** get_style('imaps', 'earthquakes!^ last_month.csv') *****"
        get_style('imaps', 'earthquakes!^ last_month.csv')
        print "##### get_style('imaps', 'earthquakes!^ last_month.csv') #####"

        print "***** set_style('imaps', 'earthquakes!^ last_month.csv', 'new drawing info') *****"
        set_style('imaps', 'earthquakes!^ last_month.csv', 'new drawing info')
        print "##### set_style('imaps', 'earthquakes!^ last_month.csv', 'new drawing info') #####"

    def test_share_data(self):

        print "***** list_shared_data('zhr101') *****"
        list_shared_data("zhr101")
        print "##### list_shared_data('zhr101') #####"

        print "***** share_data('imaps', 'earthquakes!^ last_month.csv', 'zhr101') *****"
        share_data('imaps', 'earthquakes!^ last_month.csv', 'zhr101')
        print "##### share_data('imaps', 'earthquakes!^ last_month.csv', 'zhr101') #####"

        print "***** share_data('imaps', 'Public_School_Locations.zip', 'zhr101') *****"
        share_data('imaps', 'Public_School_Locations.zip', 'zhr101')
        print "##### share_data('imaps', 'Public_School_Locations.zip', 'zhr101') #####"


if __name__ == "__main__":
    _init_app(CONFIG_FILE)

    if config["app_mode"] == "web_deploy":
        response()

    elif config["app_mode"] == "unit_test":
        unittest.main()
