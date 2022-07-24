import logging
import logging.config
import os
import yaml
import urllib3

from pathlib import Path


basedir = os.path.abspath(os.path.dirname(__file__))
ontoloader_app_config = Path(os.environ.get('qa-webapi_app_config', str(Path(basedir) / 'config_local.yaml')))
ontoloader_log_config = Path(os.environ.get('qa-webapi_log_config', str(Path(basedir) / 'logging_local.yaml')))


"""Setup logging configuration
"""
with open(str(ontoloader_log_config), 'rt') as f:
    log_config = yaml.safe_load(f.read())
logging.config.dictConfig(log_config)


logger = logging.getLogger(__name__)

logger.info('USE ontoloader_app_config=%s, ontoloader_log_config=%s', ontoloader_app_config, ontoloader_log_config)

"""Setup app config
"""
with open(str(ontoloader_app_config), 'rt') as f:
    CONFIGURATION = yaml.safe_load(f.read())


app_version = os.environ.get('QAWEBAPI_APP_VERSION', None)
if app_version:
    CONFIGURATION['VERSION'] = app_version
else:
    CONFIGURATION['VERSION'] = CONFIGURATION.get('VERSION', 'SNAPSHOT-0.0.1')


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


google_creds_var_name = 'GOOGLE_APPLICATION_CREDENTIALS'
if not os.environ.get(google_creds_var_name, None):
    gcp_key_path = CONFIGURATION['DIALOGFLOW'].get('GCP_KEY', None)
    if gcp_key_path:
        gcp_key_path = Path(gcp_key_path)

        if gcp_key_path.is_absolute():
            os.environ[google_creds_var_name] = str(gcp_key_path)
        else:
            os.environ[google_creds_var_name] = str(Path(basedir) / gcp_key_path)
