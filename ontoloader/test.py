import os
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

import logging
logger = logging.getLogger(__name__)

OS_VAR = True
NUM_PARALLEL_EXEC_UNITS = 80

TABLES_DETECTORS_POOL = ThreadPoolExecutor(max_workers=16)

def run_prediction(i):
    if i == 3:
        time.sleep(5)
    print(i)
    return i

if __name__ == "__main__":
    num_of_runs = 16
    num_sample_per_runs = 256
    batch = 32
    total_image = []
    total_coord = []

    tasks = []
    results = []

    all_start_time = time.time()
    for idx in range(num_of_runs):
        tasks.append(TABLES_DETECTORS_POOL.submit(run_prediction, idx+1))

    for task in tasks:
        try:
            results.append(task.result())
        except Exception as exc:
            logger.exception('Can not get detection results')
            raise exc

    all_end_time = time.time()
    print("Average Inference run takes {} seconds.".format((all_end_time-all_start_time)/(num_of_runs*num_sample_per_runs)))
