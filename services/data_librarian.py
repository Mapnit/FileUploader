import os, datetime, re, logging, random
import xml.etree.cElementTree as Et
import unittest

# app deployment config
DEPLOY_ROOT = r"C:\Users\kdb086\Projects\CgiPythonProject"

# app runtime config
CONFIG_FILE = os.path.join(DEPLOY_ROOT, "web.config")

FILE_PATH_SEP = ';'
NAME_MAX_LENGTH = 23

ARCHIVE_FOLDER = 'archive'
ARCHIVE_FILE_EXTENSION = '.arv'

FILE_TYPES = [".csv", '.zip', '.kml', '.kmz', '.gpx']

KML_SHP_TYPES = ['Points', 'Polylines', 'Polygons']

logging.basicConfig(filename=os.path.join(os.path.join(DEPLOY_ROOT, "logs"), "data_librarian.log"),
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    level=logging.DEBUG)


# global config variable
config = {}


# load env variables in the config file
def _init_app(config_file):
    logging.debug("init config file: %s" % config_file)
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
# add the cache registry into the database
# - require cx_Oracle
#
def _register_cache_ora(username, filename, cache_file_path, data_name, status, total_row_count, cached_row_count):

    if 'db_conn' not in config.keys():
        return False
    if 'data_delete' not in config.keys():
        return False
    if 'data_insert' not in config.keys():
        return False

    src_file_path = os.path.join(os.path.join(config['store'], username), filename)
    try:
        src_modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(src_file_path))
        src_file_size = os.path.getsize(src_file_path)

        import cx_Oracle
        db_conn = None
        row_cur = None
        try:
            db_conn = cx_Oracle.connect(config['db_conn'])
            row_cur = db_conn.cursor()
            # delete the old one
            row_cur.prepare(config['data_delete'])
            row_cur.execute(None, {'owner': username, 'src_file_path': filename})
            # add the new one
            row_cur.prepare(config['data_insert'])
            row_cur.execute(None, {'owner': username, 'src_file_path': filename, 'cache_file_path': cache_file_path,
                                   'data_name': data_name, 'upload_status': status,
                                   'data_size': src_file_size,
                                   'total_row_count': total_row_count, 'cached_row_count': cached_row_count,
                                   'last_modified': src_modified_time, 'last_uploaded': datetime.datetime.now()})
            db_conn.commit()
            logging.info("register cache of [%s] [%s]: [%s]" % (username, filename, cache_file_path))
            return True
        except cx_Oracle.DatabaseError as e:
            logging.error('error in register_cache: ' + str(e))
            return False
        finally:
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        logging.error('error in register_cache: ' + str(e))
        return False


def _register_cache_lite(username, filename, cache_file_path, data_name, status, total_row_count, cached_row_count):

    if 'db_conn' not in config.keys():
        return False
    if 'data_delete' not in config.keys():
        return False
    if 'data_insert' not in config.keys():
        return False

    src_file_path = os.path.join(os.path.join(config['store'], username), filename)
    try:
        src_modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(src_file_path))
        src_file_size = os.path.getsize(src_file_path)

        import sqlite3 as sqlite
        db_conn = None
        row_cur = None
        try:
            db_conn = sqlite.connect(config['db_conn'])
            row_cur = db_conn.cursor()
            # delete the old one
            row_cur.execute(config['data_delete'], {'owner': username, 'src_file_path': filename})
            # add the new one
            row_cur.execute(config['data_insert'], {'owner': username,
                                                    'src_file_path': filename,
                                                    'cache_file_path': cache_file_path,
                                                    'data_name': data_name,
                                                    'upload_status': status,
                                                    'data_size': src_file_size,
                                                    'total_row_count': total_row_count,
                                                    'cached_row_count': cached_row_count,
                                                    'last_modified': src_modified_time,
                                                    'last_uploaded': datetime.datetime.now()})
            db_conn.commit()
            logging.info("register cache of [%s] [%s]: [%s]" % (username, filename, cache_file_path))
            return True
        except sqlite.DatabaseError as e:
            logging.error('error in register_cache: ' + str(e))
            return False
        finally:
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        logging.error('error in register_cache: ' + str(e))
        return False


def _register_cache(username, filename, cache_file_path, data_name,
                    status='READY', total_row_count=0, cached_row_count=0):
    if config["db_provider"] == "oracle":
        return _register_cache_ora(username, filename, cache_file_path, data_name,
                                   status, total_row_count, cached_row_count)
    else:  # default
        return _register_cache_lite(username, filename, cache_file_path, data_name,
                                    status, total_row_count, cached_row_count)


#
# get the data status from the cache registry
# - require cx_Oracle
#
def _get_status_ora(username, filename):

    if 'db_conn' not in config.keys():
        return None
    if 'status_query' not in config.keys():
        return None

    try:
        import cx_Oracle
        db_conn = None
        row_cur = None
        row = None
        try:
            db_conn = cx_Oracle.connect(config['db_conn'])
            row_cur = db_conn.cursor()
            # query the status
            row_cur.prepare(config['status_query'])
            row_cur.execute(None, {'owner': username, 'src_file_path': filename})
            row = row_cur.fetchone()
            if row is not None:
                return row[0]
            else:
                logging.info("no such entry [%s] [%s]" % (username, filename))
                return None
        except cx_Oracle.DatabaseError as e:
            logging.error('error in get_status: ' + str(e))
            return None
        finally:
            row = None
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        logging.error('error in get_status: ' + str(e))
        return None


def _get_status_lite(username, filename):

    if 'db_conn' not in config.keys():
        return None
    if 'status_query' not in config.keys():
        return None

    try:
        import sqlite3 as sqlite
        db_conn = None
        row_cur = None
        row = None
        try:
            db_conn = sqlite.connect(config['db_conn'])
            row_cur = db_conn.cursor()
            # query the status
            row_cur.execute(config['status_query'], {'owner': username, 'src_file_path': filename})
            row = row_cur.fetchone()
            if row is not None:
                return row[0]
            else:
                logging.info("no such entry [%s] [%s]" % (username, filename))
                return None
        except sqlite.DatabaseError as e:
            logging.error('error in get_status: ' + str(e))
            return None
        finally:
            row = None
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        logging.error('error in get_status: ' + str(e))
        return None


def get_status(username, filename):
    if config["db_provider"] == "oracle":
        return _get_status_ora(username, filename)
    else:  # default
        return _get_status_lite(username, filename)


#
# compare the file stats with the metadata in the database
# and check if the user file has been updated since last delivery
# and get the path of the data cache
# - require cx_Oracle
#
def _get_cache_ora(username, filename):

    if 'db_conn' not in config.keys():
        return None
    if 'data_query' not in config.keys():
        return None

    src_file_path = os.path.join(os.path.join(config['store'], username), filename)
    try:
        src_modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(src_file_path))
        # src_file_size = os.path.getsize(src_file_path)

        import cx_Oracle
        db_conn = None
        row_cur = None
        try:
            logging.debug("check the cache registry: " + config['db_conn'])
            db_conn = cx_Oracle.connect(config['db_conn'])
            row_cur = db_conn.cursor()
            # update the last accessed time if any
            row_cur.prepare(config['data_touch'])
            row_cur.execute(None, {'owner': username, 'src_file_path': filename,
                                   'last_accessed': datetime.datetime.now()})
            db_conn.commit()
            # query the cache registry
            row_cur.prepare(config['data_query'])
            row_cur.execute(None, {'owner': username, 'src_file_path': filename})
            row = row_cur.fetchone()  # user_name and file_name are made up as Primary key
            if row is not None:
                last_modified_date = row[0]
                cache_file_paths_string = str(row[1])
                if last_modified_date is not None and cache_file_paths_string is not None:
                    time_delta = src_modified_time - last_modified_date
                    logging.debug("the cache expires by " + str(time_delta))
                    if abs(time_delta.total_seconds()) < 1:
                        cache_file_paths = cache_file_paths_string.split(FILE_PATH_SEP)
                        cache_exists = True
                        for file_path in cache_file_paths:
                            cache_exists = cache_exists and os.path.exists(file_path)
                            if not cache_exists:
                                logging.debug("the cache file not found at " + file_path)
                                break
                        if cache_exists:
                            logging.info("valid cache of [%s] [%s]: [%s]"
                                         % (username, filename, cache_file_paths_string))
                            return cache_file_paths_string
            return None
        except cx_Oracle.DatabaseError as e:
            logging.error('error in get_cache: ' + str(e))
            return None
        finally:
            row = None
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        logging.error('error in get_cache: ' + str(e))
        return None


def _get_cache_lite(username, filename):

    if 'db_conn' not in config.keys():
        return None
    if 'data_query' not in config.keys():
        return None

    src_file_path = os.path.join(os.path.join(config['store'], username), filename)
    try:
        src_modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(src_file_path))
        # src_file_size = os.path.getsize(src_file_path)

        import sqlite3 as sqlite
        db_conn = None
        row_cur = None
        row = None
        try:
            logging.debug("check the cache registry: " + config['db_conn'])
            db_conn = sqlite.connect(config['db_conn'])
            row_cur = db_conn.cursor()
            row_cur.execute(config['data_touch'], {'owner': username, 'src_file_path': filename,
                                                   'last_accessed': datetime.datetime.now()})
            db_conn.commit()
            row_cur.execute(config['data_query'], {'owner': username, 'src_file_path': filename})
            row = row_cur.fetchone()  # user_name and file_name are made up as Primary key
            if row is not None:
                # ignore the millisecond
                last_modified_date = datetime.datetime.strptime(row[0].split('.')[0], "%Y-%m-%d %H:%M:%S")
                cache_file_paths_string = str(row[1])
                if last_modified_date is not None and cache_file_paths_string is not None:
                    time_delta = src_modified_time - last_modified_date
                    logging.debug("the cache expires by " + str(time_delta))
                    if abs(time_delta.total_seconds()) < 1:
                        cache_file_paths = cache_file_paths_string.split(FILE_PATH_SEP)
                        cache_exists = True
                        for file_path in cache_file_paths:
                            cache_exists = cache_exists and os.path.exists(file_path)
                            if not cache_exists:
                                logging.debug("the cache file not found at " + file_path)
                                break
                        if cache_exists:
                            logging.info("valid cache of [%s] [%s]: [%s]"
                                         % (username, filename, cache_file_paths_string))
                            return cache_file_paths_string
            return None
        except sqlite.DatabaseError as e:
            logging.error('error in get_cache: ' + str(e))
            return None
        finally:
            row = None
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        logging.error('error in get_cache: ' + str(e))
        return None


def _get_cache(username, filename):
    if config["db_provider"] == "oracle":
        return _get_cache_ora(username, filename)
    else:  # default
        return _get_cache_lite(username, filename)


#
# move the source data file into an archive folder
#
def _archive_data_file(username, filename):
    user_folder = os.path.join(config['store'], username)
    src_file_path = os.path.join(user_folder, filename)

    if not os.path.exists(src_file_path):
        logging.warn('no such data file [%s]' % filename)
        # print '{"error": "no such data file [%s]", "scope":"env"}' % filename
        return None

    else:
        archive_folder_path = os.path.join(user_folder, ARCHIVE_FOLDER)
        if not os.path.exists(archive_folder_path):
            os.mkdir(archive_folder_path)

        archive_ts = datetime.datetime.now().strftime("%Y_%m_%d-%H_%M_%S")

        archive_file_path = os.path.join(archive_folder_path, filename + "(" + archive_ts + ")" + ARCHIVE_FILE_EXTENSION)
        os.rename(src_file_path, archive_file_path)

        return archive_file_path


#
# archive a data file, including its cache registry
#
def _archive_data_ora(username, filename, archive_file_path, retain_style=False):
    if 'db_conn' not in config.keys():
        return False
    if 'data_archive' not in config.keys():
        return False
    if 'data_delete' not in config.keys():
        return False
    if retain_style is True and 'style_delete' not in config.keys():
        return False

    try:
        import cx_Oracle
        db_conn = None
        row_cur = None
        try:
            db_conn = cx_Oracle.connect(config['db_conn'])
            row_cur = db_conn.cursor()
            if archive_file_path is None:
                logging.warn("delete the orphan registry (source file is missing)")
            else:
                # move the registry to the archived table
                row_cur.prepare(config['data_archive'])
                row_cur.execute(None, {'owner': username,
                                       'src_file_path': filename,
                                       'arv_file_path': archive_file_path,
                                       'archived': datetime.datetime.now()})
            row_cur.prepare(config['data_delete'])
            row_cur.execute(None, {'owner': username,
                                   'src_file_path': filename})
            # delete the associated style record
            if retain_style is False:
                row_cur.prepare(config['style_delete'])
                row_cur.execute(None, {'owner': username,
                                       'src_file_path': filename})
            # commit changes
            db_conn.commit()
            logging.info("archived [%s] [%s] into [%s] (style %s deleted)"
                         % (username, filename, archive_file_path, ("not" if retain_style is True else "is")))
            return True
        except cx_Oracle.DatabaseError as e:
            logging.error('error in archive_data: ' + str(e))
            return False
        finally:
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        logging.error('error in archive_data: ' + str(e))
        return False


def _archive_data_lite(username, filename, archive_file_path, retain_style=False):
    if 'db_conn' not in config.keys():
        return False
    if 'data_archive' not in config.keys():
        return False
    if 'data_delete' not in config.keys():
        return False
    if retain_style is True and 'style_delete' not in config.keys():
        return False

    try:
        import sqlite3 as sqlite
        db_conn = None
        row_cur = None
        try:
            db_conn = sqlite.connect(config['db_conn'])
            row_cur = db_conn.cursor()
            if archive_file_path is None:
                logging.warn("delete the orphan registry (source file is missing)")
            else:
                # move the registry to the archived table
                row_cur.execute(config['data_archive'], {'owner': username,
                                                         'src_file_path': filename,
                                                         'arv_file_path': archive_file_path,
                                                         'archived': datetime.datetime.now()})
            row_cur.execute(config['data_delete'], {'owner': username,
                                                    'src_file_path': filename})
            # delete the associated style record
            if retain_style is False:
                row_cur.execute(config['style_delete'], {'owner': username,
                                                         'src_file_path': filename})
            db_conn.commit()
            logging.info("archived [%s] [%s] into [%s] (style %s deleted)"
                         % (username, filename, archive_file_path, ("not" if retain_style is True else "is")))
            return True
        except sqlite.DatabaseError as e:
            logging.error('error in archive_data: ' + str(e))
            return False
        finally:
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        logging.error('error in archive_data: ' + str(e))
        return False


def archive_data(username, filename, retain_style=False):
    archive_file_path = _archive_data_file(username, filename)

    if config["db_provider"] == "oracle":
        return _archive_data_ora(username, filename, archive_file_path, retain_style)
    else:  # default
        return _archive_data_lite(username, filename, archive_file_path, retain_style)


#
# update the user-defined name (data_name)
#
def _rename_data_ora(username, filename, new_data_name):
    if 'db_conn' not in config.keys():
        return False
    if 'data_rename' not in config.keys():
        return False

    try:
        import cx_Oracle
        db_conn = None
        row_cur = None
        try:
            db_conn = cx_Oracle.connect(config['db_conn'])
            row_cur = db_conn.cursor()
            # update the existing one
            row_cur.prepare(config['data_rename'])
            row_cur.execute(None, {'owner': username, 'src_file_path': filename, 'data_name': new_data_name})
            db_conn.commit()
            logging.info("rename [%s] [%s] to [%s]" % (username, filename, new_data_name))
            return True
        except cx_Oracle.DatabaseError as e:
            logging.error('error in rename_data: ' + str(e))
            return False
        finally:
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        logging.error('error in rename_data: ' + str(e))
        return False


def _rename_data_lite(username, filename, new_data_name):
    if 'db_conn' not in config.keys():
        return False
    if 'data_rename' not in config.keys():
        return False

    try:
        import sqlite3 as sqlite
        db_conn = None
        row_cur = None
        try:
            db_conn = sqlite.connect(config['db_conn'])
            row_cur = db_conn.cursor()
            # update the existing one
            row_cur.execute(config['data_rename'], {'owner': username,
                                                    'src_file_path': filename,
                                                    'data_name': new_data_name})
            db_conn.commit()
            logging.info("rename [%s] [%s] to [%s]" % (username, filename, new_data_name))
            return True
        except sqlite.DatabaseError as e:
            logging.error('error in rename_data: ' + str(e))
            return False
        finally:
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        logging.error('error in rename_data: ' + str(e))
        return False


def rename_data(username, filename, new_data_name):
    if new_data_name is None or len(new_data_name.strip()) == 0:
        print '{"error": "empty data name", "scope":"request"}'
        return False

    if config["db_provider"] == "oracle":
        return _rename_data_ora(username, filename, new_data_name)
    else:  # default
        return _rename_data_lite(username, filename, new_data_name)


#
# get the data style (drawing_info)
# return drawing_info
#
def _get_style_ora(username, filename):
    if 'db_conn' not in config.keys():
        return False
    if 'style_query' not in config.keys():
        return False

    try:
        import cx_Oracle
        db_conn = None
        row_cur = None
        row = None
        drawing_info = None
        try:
            db_conn = cx_Oracle.connect(config['db_conn'])
            row_cur = db_conn.cursor()
            # check if there is already one
            row_cur.prepare(config['style_query'])
            row_cur.execute(None, {'owner': username, 'src_file_path': filename})
            row = row_cur.fetchone()  # user_name and file_name are made up as Primary key
            if row is not None:
                drawing_info = row[0]
            logging.info("get the style of [%s] [%s]: [%s]" % (username, filename, drawing_info))
            return drawing_info
        except cx_Oracle.DatabaseError as e:
            logging.error('error in get_style: ' + str(e))
            return drawing_info
        finally:
            row = None
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        logging.error('error in get_style: ' + str(e))
        return False


def _get_style_lite(username, filename):
    if 'db_conn' not in config.keys():
        return False
    if 'style_query' not in config.keys():
        return False

    try:
        import sqlite3 as sqlite
        db_conn = None
        row_cur = None
        row = None
        drawing_info = None
        try:
            db_conn = sqlite.connect(config['db_conn'])
            row_cur = db_conn.cursor()
            # check if there is already one
            row_cur.execute(config['style_query'], {'owner': username, 'src_file_path': filename})
            row = row_cur.fetchone()  # user_name and file_name are made up as Primary key
            if row is not None:
                drawing_info = row[0]
            logging.info("get the style of [%s] [%s]: [%s]" % (username, filename, drawing_info))
            return drawing_info
        except sqlite.DatabaseError as e:
            logging.error('error in get_style: ' + str(e))
            return drawing_info
        finally:
            row = None
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        logging.error('error in get_style: ' + str(e))
        return False


def get_style(username, filename):
    if config["db_provider"] == "oracle":
        return _get_style_ora(username, filename)
    else:  # default
        return _get_style_lite(username, filename)


#
# set the data style (drawing_info)
#
def _set_style_ora(username, filename, drawing_info):
    if 'db_conn' not in config.keys():
        return False
    if 'style_query' not in config.keys():
        return False
    if 'style_insert' not in config.keys():
        return False
    if 'style_update' not in config.keys():
        return False

    try:
        import cx_Oracle
        db_conn = None
        row_cur = None
        row = None
        try:
            db_conn = cx_Oracle.connect(config['db_conn'])
            row_cur = db_conn.cursor()
            # check if there is already one
            row_cur.prepare(config['style_query'])
            row_cur.execute(None, {'owner': username, 'src_file_path': filename})
            row = row_cur.fetchone()  # user_name and file_name are made up as Primary key
            if row is not None:
                # update the existing one
                row_cur.prepare(config['style_update'])
                row_cur.execute(None, {'owner': username, 'src_file_path': filename, 'drawing_info': drawing_info})
            else:
                # insert a new one
                row_cur.prepare(config['style_insert'])
                row_cur.execute(None, {'owner': username, 'src_file_path': filename, 'drawing_info': drawing_info})
            # commit changes
            db_conn.commit()
            logging.info("set the style of [%s] [%s]: [%s]" % (username, filename, drawing_info))
            return True
        except cx_Oracle.DatabaseError as e:
            logging.error('error in set_style: ' + str(e))
            return False
        finally:
            row = None
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        logging.error('error in set_style: ' + str(e))
        return False


def _set_style_lite(username, filename, drawing_info):
    if 'db_conn' not in config.keys():
        return False
    if 'style_query' not in config.keys():
        return False
    if 'style_insert' not in config.keys():
        return False
    if 'style_update' not in config.keys():
        return False

    try:
        import sqlite3 as sqlite
        db_conn = None
        row_cur = None
        row = None
        try:
            db_conn = sqlite.connect(config['db_conn'])
            row_cur = db_conn.cursor()
            # check if there is already one
            row_cur.execute(config['style_query'], {'owner': username, 'src_file_path': filename})
            row = row_cur.fetchone()  # user_name and file_name are made up as Primary key
            if row is not None:
                # update the existing one
                row_cur.execute(config['style_update'], {'owner': username,
                                                         'src_file_path': filename,
                                                         'drawing_info': drawing_info})
            else:
                # insert a new one
                row_cur.execute(config['style_insert'], {'owner': username,
                                                         'src_file_path': filename,
                                                         'drawing_info': drawing_info})
            # commit changes
            db_conn.commit()

            logging.info("set the style of [%s] [%s]: [%s]" % (username, filename, drawing_info))
            return True
        except sqlite.DatabaseError as e:
            logging.error('error in set_style: ' + str(e))
            return False
        finally:
            row = None
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        logging.error('error in set_style: ' + str(e))
        return False


def set_style(username, filename, drawing_info):
    if config["db_provider"] == "oracle":
        return _set_style_ora(username, filename, drawing_info)
    else:  # default
        return _set_style_lite(username, filename, drawing_info)


#
# create a default symbol in json
#
def _get_default_style(geom_type, label=None):

    label = "" if label is None else label
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

    return '{"label": "%s", %s}' % (label, style_json)


#
# normalize a filename by removing any illegal char
#
def _normalize_name(name):
    return '_'.join(re.split('[\W]+', name))


def _write_features_json(datapath, json_file_path):
    import arcpy
    from arcpy import env

    env.overwriteOutput = True
    logging.info("output features to json [%s]" % json_file_path)
    arcpy.FeaturesToJSON_conversion(datapath, json_file_path)  # , "FORMATTED"


def _output_feature_json(json_file_paths, output_name=None):
    count = 0
    print "["
    for file_path in json_file_paths:
        if count > 0:
            print ","
        logging.info("serve json from the cache file [%s]" % file_path)
        with open(file_path, "r") as json_file:
            for txtline in json_file:
                print txtline
        count += 1
    print "]"


# create a layer of features fewer than the defined max number of rows
# return the filtered layer, total row count, filtered row count
#
def _filter_data_by_count(file_path, oid_column, stg_workspace, extra_name=""):

    import arcpy
    from arcpy import env

    env.overwriteOutput = True

    fname, fext = os.path.splitext(os.path.basename(file_path))
    fname = fname[0:NAME_MAX_LENGTH]
    extra_name = "" if extra_name is None else extra_name.strip()

    stats_fields = [[oid_column, "MIN"]]
    stats_table = os.path.join(stg_workspace, "%s_%s_stats" % (fname, extra_name))
    filtered_layer_name = "%s_%s_filtered_layer" % (fname, extra_name)
    # filtered_file_path = os.path.join(stg_workspace, "%s_%s_filtered%s" % (fname, extra_name, fext))

    logging.info("calculate the feature count")
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
        logging.info("limit the number of features (%i) to %i" % (cnt_oid, max_count))
        where_clause = "%s < %i" % (oid_column, min_oid + max_count)
        arcpy.MakeFeatureLayer_management(file_path, filtered_layer_name, where_clause)
        # arcpy.CopyFeatures_management(filtered_layer_name, filtered_file_path)
        # return filtered_file_path
        return filtered_layer_name, cnt_oid, max_count
    else:
        logging.info("no limit since the number of features (%i) is less than %i" % (cnt_oid, max_count))
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
    # stg_fgdb_path = os.path.join(stg_folder, stg_fgdb_name)
    stg_fgdb_path = "in_memory"

    import arcpy
    from arcpy import env

    env.overwriteOutput = True
    output_spatial_ref = arcpy.SpatialReference(int(config["output_wkid"]))

    stg_json_path_string = None

    total_row_count = 0
    filtered_row_count = 0

    carto_styles_string = get_style(username, filename)
    carto_styles_array = []

    if fext == ".zip":  # zipped shapefile
        # unzip the zip file
        logging.info("unzip file [%s] to [%s]" % (src_file_path, stg_folder))
        import zipfile
        with zipfile.ZipFile(src_file_path, "r") as zipShpFile:
            zipShpFile.extractall(stg_folder)
            namelist = zipShpFile.namelist()
            unzip_base, unzip_ext = os.path.splitext(namelist[0])
            unzip_dir = os.path.dirname(unzip_base)
            unzip_base = os.path.basename(unzip_base)
            stg_data_path = os.path.join(os.path.join(stg_folder, unzip_dir), unzip_base + ".shp")
            logging.info("unzipped shape file [%s]" % stg_data_path)

        data_despt = arcpy.Describe(stg_data_path)
        # assign default symbology
        if carto_styles_string is None:
            carto_styles_array.append(_get_default_style(data_despt.shapeType))
        # limit data by count
        stg_data_path, total_row_count, filtered_row_count = \
            _filter_data_by_count(stg_data_path, data_despt.OIDFieldName, stg_folder)
        # transform or project to the standard spatial ref
        src_spatial_ref = data_despt.spatialReference
        if src_spatial_ref.name != output_spatial_ref.name:
            stg_prep_file_path = os.path.join(os.path.join(stg_folder, unzip_dir), unzip_base + "_prep.shp")
            arcpy.Project_management(stg_data_path, stg_prep_file_path, output_spatial_ref)
            stg_data_path = stg_prep_file_path

        # write features to json
        stg_json_path_string = os.path.join(cache_folder, fname + ".json")
        _write_features_json(stg_data_path, stg_json_path_string)

        # cleanup
        # arcpy.Delete_management(stg_data_path)

    elif fext == ".gpx":  # gpx
        if not arcpy.Exists(stg_fgdb_path):
            logging.info("create fgdb [%s] under [%s]" % (stg_fgdb_name, stg_folder))
            arcpy.CreateFileGDB_management(stg_folder, stg_fgdb_name)

        # convert to feature class
        logging.info("convert gpx [%s] to staging fgdb in [%s]" % (src_file_path, stg_fgdb_path))
        stg_data_path = os.path.join(stg_fgdb_path, fname_norm)
        arcpy.GPXtoFeatures_conversion(src_file_path, stg_data_path)

        # transform or project to the standard spatial ref
        data_despt = arcpy.Describe(stg_data_path)
        # assign default symbology
        if carto_styles_string is None:
            carto_styles_array.append(_get_default_style(data_despt.shapeType))
        # limit data by count
        stg_data_path, total_row_count, filtered_row_count = \
            _filter_data_by_count(stg_data_path, data_despt.OIDFieldName, stg_fgdb_path)
        # transform or project to the standard spatial ref
        src_spatial_ref = data_despt.spatialReference
        if src_spatial_ref.name != output_spatial_ref.name:
            stg_prep_file_path = stg_data_path + "_prep"
            arcpy.Project_management(stg_data_path, stg_prep_file_path, output_spatial_ref)
            stg_data_path = stg_prep_file_path

        # output features to json
        stg_json_path_string = os.path.join(cache_folder, fname + ".json")
        _write_features_json(stg_data_path, stg_json_path_string)

        # cleanup
        # arcpy.Delete_management(stg_data_path)

    elif fext == ".csv":  # csv
        if not arcpy.Exists(stg_fgdb_path):
            logging.info("create fgdb [%s] under [%s]" % (stg_fgdb_name, stg_folder))
            arcpy.CreateFileGDB_management(stg_folder, stg_fgdb_name)

        # convert to feature class
        logging.info("convert csv [%s] to staging fgdb in [%s]" % (src_file_path, stg_fgdb_path))
        csv_layer_name = fname_norm + "_csv_layer"
        arcpy.MakeXYEventLayer_management(src_file_path, "longitude", "latitude",
                                          csv_layer_name, output_spatial_ref)

        stg_data_path = os.path.join(stg_fgdb_path, fname_norm)
        arcpy.CopyFeatures_management(csv_layer_name, stg_data_path)

        data_despt = arcpy.Describe(stg_data_path)
        # assign default symbology
        if carto_styles_string is None:
            carto_styles_array.append(_get_default_style(data_despt.shapeType))
        # limit data by count
        stg_data_path, total_row_count, filtered_row_count = \
            _filter_data_by_count(stg_data_path, data_despt.OIDFieldName, stg_fgdb_path)
        # transform or project to the standard spatial ref
        src_spatial_ref = data_despt.spatialReference
        if src_spatial_ref.name != output_spatial_ref.name:
            stg_prep_file_path = stg_data_path + "_prep"
            arcpy.Project_management(stg_data_path, stg_prep_file_path, output_spatial_ref)
            stg_data_path = stg_prep_file_path

        # output features to json
        stg_json_path_string = os.path.join(cache_folder, fname + ".json")
        _write_features_json(stg_data_path, stg_json_path_string)

        # cleanup
        # arcpy.Delete_management(stg_data_path)

    elif fext in [".kmz", ".kml"]:  # kml/kmz
        stg_json_paths = []
        # convert to feature class
        logging.info("convert kml/kmz [%s] to staging fgdb in [%s]" % (src_file_path, stg_folder))
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
                    stg_data_path, total_count, filtered_count = \
                        _filter_data_by_count(stg_data_path, data_despt.OIDFieldName, stg_fgdb_path, shp_type)
                    # transform or project to the standard spatial ref
                    src_spatial_ref = data_despt.spatialReference
                    if src_spatial_ref.name != output_spatial_ref.name:
                        stg_prep_file_path = stg_data_path + "_prep"
                        arcpy.Project_management(stg_data_path, stg_prep_file_path, output_spatial_ref)
                        stg_data_path = stg_prep_file_path

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
        logging.error("unsupported file type: %s" % fext)

    if carto_styles_string is None:
        carto_styles_string = "[" + ",".join(carto_styles_array) + "]"

    return stg_json_path_string, carto_styles_string, total_row_count, filtered_row_count


#
# check the cache first.
# If not cached, prepare the data. Otherwise, return the cache
#
def get_data(username, filename):

    fname, fext = os.path.splitext(os.path.basename(filename))

    stg_json_path_string = _get_cache(username, filename)
    if stg_json_path_string is not None:
        logging.info("use cached data: [%s]" % stg_json_path_string)
    else:
        # merely create a registry entry
        _register_cache(username, filename, "", fname, "PROCESSING")
        # prepare data
        logging.debug("prepare data into json")
        stg_json_path_string, carto_json_string, total_row_count, cached_row_count = _prepare_data(username, filename)
        # register the data with the cache and status info
        if stg_json_path_string is not None:
            _register_cache(username, filename, stg_json_path_string, fname, "READY", total_row_count, cached_row_count)
        # set the style
        if carto_json_string is not None:
            set_style(username, filename, carto_json_string)

    # output feature as json
    if stg_json_path_string is not None:
        logging.debug("send out data")
        stg_json_paths = stg_json_path_string.split(FILE_PATH_SEP)
        _output_feature_json(stg_json_paths)


#
# list all files belonging to a given user with a filter
# (from file system)
#
def list_files(username, data_filter=None):
    list_folder = os.path.join(config['store'], username)
    logging.debug('user folder: ' + list_folder)

    try:
        count = 0
        print '['
        for fn in os.listdir(list_folder):
            fp_full = os.path.join(list_folder, fn)
            fn_base, fn_ext = os.path.splitext(fn)
            if fn_ext.lower() in FILE_TYPES and os.path.isfile(fp_full):
                logging.debug("user file: " + fp_full)
                modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(fp_full))
                file_size = os.path.getsize(fp_full)
                if count > 0:
                    print ','
                print '{"filename":"%s", "last_modified":"%s", "size":%s}' \
                      % (fn, modified_time.strftime("%Y-%m-%d %H:%M:%S"), file_size)
                count += 1
    except os.error, err:
        print '{"error": "failed to list data files", "scope":"env"}'
        logging.error('error in list_data: ' + str(err))
    finally:
        print ']'


#
# list all data files belonging to a given user
# (from data registry table in database)
#
def _list_data_ora(username, data_filter=None):
    if 'db_conn' not in config.keys():
        return None
    if 'data_list' not in config.keys():
        return None

    try:
        import cx_Oracle
        db_conn = None
        row_cur = None

        count = 0
        print '['
        try:
            logging.debug("list all data files owned by " + username)
            db_conn = cx_Oracle.connect(config['db_conn'])
            row_cur = db_conn.cursor()
            row_cur.prepare(config['data_list'])
            row_cur.execute(None, {'owner': username})
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
                print '''{"src_file_path":"%s", "data_name":"%s", "size":%s, "last_modified":"%s", "last_uploaded":"%s",
                          "upload_status":"%s", "total_row_count":%s, "cached_row_count":%s, "drawing_info":%s}''' \
                      % (src_file_path, data_name, data_size, last_modified.strftime("%Y-%m-%d %H:%M:%S"),
                         last_uploaded.strftime("%Y-%m-%d %H:%M:%S"),
                         upload_status, total_row_count, cached_row_count, drawing_info)
                count += 1
        except cx_Oracle.DatabaseError as e:
            logging.error('error in list_data: ' + str(e))
            return None
        finally:
            print ']'
            row = None
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        logging.error('error in list_data: ' + str(e))
        return None


def _list_data_lite(username, data_filter=None):
    if 'db_conn' not in config.keys():
        return None
    if 'data_list' not in config.keys():
        return None

    try:
        import sqlite3 as sqlite
        db_conn = None
        row_cur = None

        count = 0
        print '['
        try:
            logging.debug("list all data files owned by " + username)
            db_conn = sqlite.connect(config['db_conn'])
            row_cur = db_conn.cursor()
            row_cur.execute(config['data_list'], {'owner': username})
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
                print '''{"src_file_path":"%s", "data_name":"%s", "size":%s, "last_modified":"%s", "last_uploaded":"%s",
                        "upload_status":"%s", "total_row_count":%s, "cached_row_count":%s, "drawing_info":%s}''' \
                      % (src_file_path, data_name, data_size, last_modified, last_uploaded,
                         upload_status, total_row_count, cached_row_count, drawing_info)
                count += 1
        except sqlite.DatabaseError as e:
            logging.error('error in list_data: ' + str(e))
            return None
        finally:
            print ']'
            row = None
            if row_cur is not None:
                row_cur.close()
            if db_conn is not None:
                db_conn.close()

    except Exception as e:
        logging.error('error in list_data: ' + str(e))
        return None


def list_data(username, data_filter=None):
    if config["db_provider"] == "oracle":
        return _list_data_ora(username, data_filter)
    else:  # default
        return _list_data_lite(username, data_filter)


#
# web response supports four actions:
# - list, list_files, archive, rename, style
#
def response():
    import cgi
    import cgitb; cgitb.enable()  # Optional; for debugging only

    print "Content-Type: text/json"
    print

    arguments = cgi.FieldStorage()
    if 'username' not in arguments.keys():
        print '{"error": "unknown user", "scope":"request"}'
    elif 'action' not in arguments.keys():
        print '{"error": "unknown action", "scope":"request"}'
    else:
        logging.info("request parameters: ")
        for i in arguments.keys():
            logging.debug(" - " + str(i) + ": " + str(arguments[i].value))

        username = str(arguments['username'].value).lower()
        # logging.info(" - username: " + username)
        action = str(arguments['action'].value).lower()
        # logging.info(" - action: " + action)
        filters = None
        if 'filters' in arguments.keys() and arguments['filters'].value is not None:
            filters = str(arguments['filters'])
        logging.info(" - filters: " + str(filters))

        if action == 'list':
            logging.info("execute: list files satisfying filters [%s] " % str(filters))
            list_data(username, filters)

        elif action == 'list_files':
            logging.info("execute: list files satisfying filters [%s] " % str(filters))
            list_files(username, filters)

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
            logging.info("execute: list all shared files satisfying filters [%s] " % str(filters))
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

    logging.info("response completed")
    return


#
# Test Cases
#
class TestDataLibrarian(unittest.TestCase):

    def test_list_files(self):

        print "***** list_files('imaps') *****"
        list_files("imaps")
        print "##### list_files('imaps') #####"

        print "***** list_files('kdb086') *****"
        list_files("kdb086")
        print "##### list_files('kdb086') #####"

    def test_list_data(self):

        print "***** list_data('imaps') *****"
        list_data("imaps")
        print "##### list_data('imaps') #####"

        print "***** list_data('kdb086') *****"
        list_data("kdb086")
        print "##### list_data('kdb086') #####"

    def test_cache_registry(self):

        print "***** _register_cache('imaps') *****"
        _register_cache("imaps", "Wells_Active.csv", r"cache\Wells_Active.json", "Wells_Active")
        print "##### _register_cache('imaps') #####"

        print "***** _is_cached('imaps') *****"
        result = _get_cache("imaps", "Wells_Active.csv")
        assert result is None
        print "##### _is_cached('imaps') #####"

        print "***** _register_cache('kdb086') *****"
        _register_cache("kdb086", "earthquakes.csv", r"cache\earthquakes.json", "earthquakes")
        print "##### _register_cache('kdb086') #####"

        print "***** _is_cached('kdb086') *****"
        result = _get_cache("kdb086", "earthquakes.csv")
        # assert result == r'C:\Users\kdb086\Projects\CgiPythonProject\data_stage\kdb086\cache\earthquakes.json'
        assert result is None
        print "##### _is_cached('kdb086') #####"

        print "***** _is_cached('imaps') *****"
        result = _get_cache("imaps", "wells.csv")
        assert result is None
        print "##### _is_cached('imaps') #####"

    def test_get_data_imap(self):

        print "***** get_data('imaps', 'Wells_Active!^ - Copy.csv') *****"
        get_data("imaps", "Wells_Active!^ - Copy.csv")
        print "##### get_data('imaps', 'Wells_Active!^ - Copy.csv') #####"

        print "***** get_data('imaps', 'Wells_Active.csv') *****"
        get_data("imaps", "Wells_Active.csv")
        print "##### get_data('imaps', 'Wells_Active.csv') #####"

        print "***** get_data('imaps', 'DoesNotWork.zip') *****"
        get_data("imaps", "DoesNotWork.zip")
        print "##### get_data('imaps', 'DoesNotWork.zip') #####"

        print "***** get_data('imaps', 'APC(DoesNotWork).zip') *****"
        get_data("imaps", "APC(DoesNotWork).zip")
        print "##### get_data('imaps', 'APC(DoesNotWork).zip') #####"

        print "***** get_data('imaps', 'wells.zip') *****"
        get_data("imaps", "wells.zip")
        print "##### get_data('imaps', 'wells.zip') #####"

        print "***** get_data('imaps', 'test.gpx') *****"
        get_data("imaps", "test.gpx")
        print "##### get_data('imaps', 'test.gpx') #####"

        print "***** get_data('imaps', 'KML_Samples.kml') *****"
        get_data("imaps", "KML_Samples.kml")
        print "##### get_data('imaps', 'KML_Samples.kml') #####"

    def test_get_data_kdb086(self):

        print "***** get_data('kdb086', 'earthquakes.csv') *****"
        get_data("kdb086", "earthquakes.csv")
        print "##### get_data('kdb086', 'earthquakes.csv') #####"

        print "***** get_data('kdb086', 'testShpFile.zip') *****"
        get_data("kdb086", "testShpFile.zip")
        print "##### get_data('kdb086', 'testShpFile.zip') #####"

        print "***** get_data('kdb086', 'KFC__62__2015.gpx') *****"
        get_data("kdb086", "KFC__62__2015.gpx")
        print "##### get_data('kdb086', 'KFC__62__2015.gpx') #####"

        print "***** get_data('kdb086', 'KML_Samples.kml') *****"
        get_data("kdb086", "KML_Samples.kml")
        print "##### get_data('kdb086', 'KML_Samples.kml') #####"

        print "***** get_data('kdb086', 'HighSchools.kmz') *****"
        get_data("kdb086", "HighSchools.kmz")
        print "##### get_data('kdb086', 'HighSchools.kmz') #####"

    def test_get_data_kml(self):

        print "***** get_data('kdb086', 'HighSchools.kmz') *****"
        get_data("kdb086", "HighSchools.kmz")
        print "##### get_data('kdb086', 'HighSchools.kmz') #####"

        print "***** get_data('kdb086', 'KML_Samples.kml') *****"
        get_data("kdb086", "KML_Samples.kml")
        print "##### get_data('kdb086', 'KML_Samples.kml') #####"

    def test_get_data_big(self):

        print "***** get_data('kdb086', 'APC_Equipment_Less1.zip') *****"
        get_data("kdb086", "APC_Equipment_Less1.zip")
        print "##### get_data('kdb086', 'APC_Equipment_Less1.zip') #####"

        print "***** get_data('kdb086', 'APC_Equipment_Less2.zip') *****"
        get_data("kdb086", "APC_Equipment_Less2.zip")
        print "##### get_data('kdb086', 'APC_Equipment_Less2.zip') #####"

        print "***** get_data('kdb086', 'APC_Equipment.zip') *****"
        get_data("kdb086", "APC_Equipment.zip")
        print "##### get_data('kdb086', 'APC_Equipment.zip') #####"

    def test_get_status(self):

        print "***** get_status('kdb086', 'KML_Samples.kml') *****"
        get_status("kdb086", "KML_Samples.kml")
        print "##### get_status('kdb086', 'KML_Samples.kml') #####"

        print "***** get_status('kdb086', 'earthquakes.csv') *****"
        get_status("kdb086", "earthquakes.csv")
        print "##### get_status('kdb086', 'earthquakes.csv') #####"

    def _test_archive_data(self):

        print "***** get_data('kdb086', 'HighSchools.kmz') *****"
        get_data("kdb086", "HighSchools.kmz")
        print "##### get_data('kdb086', 'HighSchools.kmz') #####"

        print "***** archive_data('kdb086', 'HighSchools.kmz') *****"
        archive_data("kdb086", "HighSchools.kmz")
        print "##### archive_data('kdb086', 'HighSchools.kmz') #####"

        print "***** get_data('kdb086', 'HighSchools.kmz') *****"
        get_data("kdb086", "HighSchools.kmz")
        print "##### get_data('kdb086', 'HighSchools.kmz') #####"

    def _test_rename_data(self):

        print "***** list_data('imaps') *****"
        list_data("imaps")
        print "##### list_data('imaps') #####"

        print "***** rename_data('imaps', 'DoesNotWork.zip', 'Worked actually') *****"
        rename_data("imaps", "DoesNotWork.zip", "Worked actually")
        print "##### rename_data('imaps', 'DoesNotWork.zip', 'Worked actually') #####"

        print "***** list_data('imaps') *****"
        list_data("imaps")
        print "##### list_data('imaps') #####"

    def _test_style_data(self):

        print "***** list_data('kdb086') *****"
        list_data("kdb086")
        print "##### list_data('kdb086') #####"

        print "***** get_style('kdb086', 'earthquakes.csv') *****"
        get_style('kdb086', 'earthquakes.csv')
        print "##### get_style('kdb086', 'earthquakes.csv') #####"

        print "***** set_style('kdb086', 'earthquakes.csv', 'new drawing info') *****"
        set_style('kdb086', 'earthquakes.csv', 'new drawing info')
        print "##### set_style('kdb086', 'earthquakes.csv', 'new drawing info') #####"

        print "***** get_style('kdb086', 'earthquakes.csv') *****"
        get_style('kdb086', 'earthquakes.csv')
        print "##### get_style('kdb086', 'earthquakes.csv') #####"

        print "***** list_data('kdb086') *****"
        list_data("kdb086")
        print "##### list_data('kdb086') #####"

    def test_share_data(self):

        print "***** list_shared_data('zhr101') *****"
        list_shared_data("zhr101")
        print "##### list_shared_data('zhr101') #####"

        print "***** share_data('kdb086', 'earthquakes.csv', 'zhr101') *****"
        share_data('kdb086', 'earthquakes.csv', 'zhr101')
        print "##### share_data('kdb086', 'earthquakes.csv', 'zhr101') #####"

        print "***** share_data('kdb086', 'APC_Equipment.zip', 'zhr101') *****"
        share_data('kdb086', 'APC_Equipment.zip', 'zhr101')
        print "##### share_data('kdb086', 'APC_Equipment.zip', 'zhr101') #####"

        print "***** share_data('kdb086', 'APC_Equipment.zip', 'wqx202') *****"
        share_data('kdb086', 'APC_Equipment.zip', 'wqx202')
        print "##### share_data('kdb086', 'APC_Equipment.zip', 'wqx202') #####"

        print "***** list_shared_users('kdb086', 'earthquakes.csv') *****"
        list_shared_users('kdb086', 'earthquakes.csv')
        print "##### list_shared_users('kdb086', 'earthquakes.csv') #####"

        print "***** list_shared_data('zhr101') *****"
        list_shared_data("zhr101")
        print "##### list_shared_data('zhr101') #####"

        print "***** list_shared_users('kdb086', 'APC_Equipment.zip') *****"
        list_shared_users('kdb086', 'APC_Equipment.zip')
        print "##### list_shared_users('kdb086', 'APC_Equipment.zip') #####"

        print "***** revoke_share('kdb086', 'earthquakes.csv', 'zhr101') *****"
        revoke_share('kdb086', 'earthquakes.csv', 'zhr101')
        print "##### revoke_share('kdb086', 'earthquakes.csv', 'zhr101') #####"

        print "***** list_shared_data('zhr101') *****"
        list_shared_data("zhr101")
        print "##### list_shared_data('zhr101') #####"

        print "***** revoke_all_shares('kdb086', 'APC_Equipment.zip') *****"
        revoke_all_shares('kdb086', 'APC_Equipment.zip')
        print "##### revoke_all_shares('kdb086', 'APC_Equipment.zip') #####"

        print "***** list_shared_data('wqx202') *****"
        list_shared_data("wqx202")
        print "##### list_shared_data('wqx202') #####"

if __name__ == "__main__":
    _init_app(CONFIG_FILE)

    if config["app_mode"] == "web_deploy":
        response()

    elif config["app_mode"] == "unit_test":
        unittest.main()
