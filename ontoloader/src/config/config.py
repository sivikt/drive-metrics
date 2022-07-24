import logging
import logging.config
import os
import yaml

from pathlib import Path


basedir = Path(os.path.abspath(os.path.dirname(__file__)))

ontoloader_app_config = Path(os.environ.get('ONTOLOADER_APP_CONFIG', str(basedir / 'config_local.yaml')))
ontoloader_log_config = Path(os.environ.get('ONTOLOADER_LOG_CONFIG', str(basedir / 'logging_local.yaml')))
ontoloader_repo_config = Path(os.environ.get('ONTOLOADER_REPO_CONFIG', str(basedir / 'local_repo-config.ttl')))


"""Setup logging configuration
"""
with open(str(ontoloader_log_config), 'rt') as f:
    log_config = yaml.safe_load(f.read())
logging.config.dictConfig(log_config)


logger = logging.getLogger(__name__)

logger.info('USE ONTOLOADER_APP_CONFIG=%s, ONTOLOADER_LOG_CONFIG=%s', ontoloader_app_config, ontoloader_log_config)

"""Setup app config
"""
with open(str(ontoloader_app_config), 'rt') as f:
    CONFIGURATION = yaml.safe_load(f.read())


app_version = os.environ.get('ONTOLOADER_APP_VERSION', None)
if app_version:
    CONFIGURATION['VERSION'] = app_version
else:
    CONFIGURATION['VERSION'] = CONFIGURATION.get('VERSION', 'SNAPSHOT-0.0.1')


is_fresh_update = os.environ.get('ONTOLOADER_DB_FRESH_UPDATE', 'False').lower()
if is_fresh_update == 'true':
    CONFIGURATION['DB_FRESH_UPDATE'] = True
    CONFIGURATION['DB_REPOS_CONFIG'] = ontoloader_repo_config
    CONFIGURATION['DB_ONTOLOGY_PTH'] = basedir.parent.parent / 'ontologies' / 'dmsmodels' / 'tripOnto-0.0.1.ttl'
else:
    CONFIGURATION['DB_FRESH_UPDATE'] = False
