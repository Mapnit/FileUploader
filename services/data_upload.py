import os, datetime, types, logging, shutil
import xml.etree.cElementTree as Et
import msvcrt

msvcrt.setmode(0, os.O_BINARY)  # stdin  = 0
msvcrt.setmode(1, os.O_BINARY)  # stdout = 1

# app deployment config
DEPLOY_ROOT = r"C:\inetpub\wwwroot\chen_test\services"

# app runtime config
CONFIG_FILE = os.path.join(DEPLOY_ROOT, "web.config")

logging.basicConfig(filename=os.path.join(os.path.join(DEPLOY_ROOT, "logs"), "data_upload.log"),
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    level=logging.DEBUG)

# app-wide constants
UPLOAD_HTML_PARAM = "uploadedfile"
# UPLOAD_FLASH_PARAM = "uploadedfileflash"

# global config variable
config = {}


# load env variables in the config file
def _init_app(config_file):
    xml_file = None
    try:
        xml_file = Et.parse(config_file)
        xml_root = xml_file.getroot()
        for kv_pair in xml_root.findall("./appSettings/add"):
            k = kv_pair.get('key')
            v = kv_pair.get('value')
            config[k] = v
    except Et.ParseError, e:
        print "{'error': 'config parse error. %s', 'scope':'env'}" % e
    except os.error, e:
        print "{'error': 'config file not found. %s', 'scope':'env'}" % e
    finally:
        del xml_file
    return


def _decorateResponse(rawResponse, ajax):
    if ajax == "iframe":
        return "<textarea>%s</textarea>" % rawResponse
    else: # direct ajax call
        return rawResponse


def response():
    import cgi
    import cgitb

    cgitb.enable()  # Optional; for debugging only

    arguments = cgi.FieldStorage()
    ajax = "raw"
    if 'ajax' in arguments.keys():
        ajax = arguments['ajax'].value.lower()

    if ajax == "iframe":
        print "Content-Type: text/html"
    else:
        print "Content-Type: application/json"
    print

    if 'username' not in arguments.keys():
        print _decorateResponse('{"error": "unknown user", "scope":"request"}', ajax)
    else:
        # logging.info("request parameters: ")
        # for i in arguments.keys():
        #    logging.debug(" - " + str(i) + ": " + str(arguments[i].value))

        username = str(arguments['username'].value).lower()
        logging.debug(" - username: " + username)

        # expect the last modified time as a number
        modified_time = 0
        if 'mtime' in arguments.keys():
            modified_time = arguments['mtime'].value
            logging.debug(" - local modified time: " + modified_time)
        else:
            logging.warn(" - No local modified time provided")
        modified_time = int(modified_time)   # in seconds

        file_key = None
        if UPLOAD_HTML_PARAM in arguments.keys():
            file_key = UPLOAD_HTML_PARAM
        else:
            logging.debug(" - arguments.keys: %s" % arguments.keys)
            print _decorateResponse('{"error": "no file uploaded", "scope":"request"}', ajax)

        if file_key is not None:
            file_item = arguments[file_key]
            logging.debug("execute: save the received file [%s]" % file_item.filename)
            if not file_item.file:
                print _decorateResponse('{"error": "empty file", "scope":"request"}', ajax)
                #print "<textarea>{'error': 'empty file', 'scope':'request'}</textarea>"
            else:
                user_store = os.path.join(config["store"], username)
                if not os.path.exists(user_store):
                    os.mkdir(user_store)

                file_basename = os.path.basename(file_item.filename)
                svr_file_path = os.path.join(user_store, file_basename)
                with open(svr_file_path, 'wb') as fout:
                    shutil.copyfileobj(file_item.file, fout, 100000)

                if modified_time > 0:
                    logging.debug("set the modified time as " + str(modified_time))
                    os.utime(svr_file_path, (modified_time, modified_time))

                print _decorateResponse('{"type":"json","filepath":"%s","filename":"%s","username":"%s"}' \
                      % (file_basename, file_basename, username), ajax)
                # html - raw ajax
                # print '{"type":"json","filepath":"%s","filename":"%s","username":"%s"}' \
                #      % (file_basename, file_basename, username)
                # html - iFrame ajax
                # print '<textarea>{"type":"json","filepath":"%s","filename":"%s","username":"%s"}</textarea>' \
                #      % (file_basename, file_basename, username)
                # html - flash
                # print 'file=../data_cache/kdb086/earthquakes_output.json,name=earthquakes_output.json,type=json'

    logging.info("response completed")
    return


if __name__ == "__main__":
    _init_app(CONFIG_FILE)

    if config["app_mode"] == "web_deploy":
        response()
