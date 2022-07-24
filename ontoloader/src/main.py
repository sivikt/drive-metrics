import logging

from config.config import CONFIGURATION
from dataimport.load_new_knowledge import DataLoader
from dbupdate.db_update import DbUpdater
from utils.timer import create_elapsed_timer_str


logger = logging.getLogger(__name__)


def run():
    graphdb_cfg = dict(
        graphdb_endpoint=CONFIGURATION['GRAPHDB']['ENDPOINT'],
        repository_id=CONFIGURATION['GRAPHDB']['REPOSITORY_ID'],
        username=CONFIGURATION['GRAPHDB']['USERNAME'],
        password=CONFIGURATION['GRAPHDB']['PASSWORD']
    )

    if CONFIGURATION.get('DB_FRESH_UPDATE', False):
        db_updater = DbUpdater(**graphdb_cfg)
        # TODO finish DbUpdater
        # db_updater.fresh_update(
        #     repo_config_path=str(CONFIGURATION['DB_REPOS_CONFIG']),
        #     version=CONFIGURATION['VERSION']
        # )

    load_new_knowledge = DataLoader(
        data_graph_name=CONFIGURATION['GRAPHDB']['MAIN_TRIPS_DATA_GRAPH'],
        batch_update_size=CONFIGURATION['BATCH_UPDATE_SIZE'],
        neo4j_endpoint=CONFIGURATION['NEO4J_ENDPOINT'],
        **graphdb_cfg
    )

    sw = create_elapsed_timer_str('sec')

    load_new_knowledge.sync()

    logger.info('Finished sync in %s', sw())


run()
