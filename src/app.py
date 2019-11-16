import argparse
import json
import os
import subprocess
import threading
from functools import reduce

from flask import Flask, request, jsonify
from time import sleep

app = Flask(__name__)

SIMBAD_ANALYZER_RUN_SCRIPT_PATH = os.getenv('SIMBAD_ANALYZER_RUN_SCRIPT_PATH', './scripts/mock/run.sh')
SIMBAD_ANALYZER_STATUS_SCRIPT_PATH = os.getenv('SIMBAD_ANALYZER_STATUS_SCRIPT_PATH', './scripts/mock/status.sh')
SIMBAD_ANALYZER_RESULT_SCRIPT_PATH = os.getenv('SIMBAD_ANALYZER_RESULT_SCRIPT_PATH', './scripts/mock/result.sh')
POLLING_PERIOD = 3


runtime_info: dict = {}
analyzer_status: dict = {"status": "IDLE"}
analyzer_result: list = []

expected_files = [
    "time_points.parquet"
    "large_clones.parquet"
    "clone_snapshots.parquet"
    "final_snapshot.csv"
    "clone_stats.parquet"
    "clone_stats_scalars.parquet"
    "large_muller_order.parquet"
    "muller_data.parquet"
    "final_mutation_freq.parquet"
    "clone_counts.parquet"
    "large_final_mutations.parquet"
]


def start_analyzer(path: str) -> None:
    """
    Starts analyzer job and spawns thread that updates
    analyzer runtime info. The workdir for simulation process is the same as
    CLI output file dir
    :param path: the path to CLI output file
    :return:
    """
    os.environ["SIMBAD_ANALYZER_WORKDIR"] = os.path.dirname(path)
    subprocess.Popen((SIMBAD_ANALYZER_RUN_SCRIPT_PATH, path))
    thread = threading.Thread(target=update_runtime_info)
    thread.daemon = True
    thread.start()
    return


def update_runtime_info() -> None:
    """
    Periodically update runtime info of current analyzer job
    :return:
    """
    workdir = os.getenv('SIMBAD_ANALYZER_WORKDIR')
    while runtime_info['finished'] is not True:
        num_expected_files: int = len(expected_files)
        num_existing_files: int = reduce(
            lambda num, file: num + (1 if os.path.exists(workdir + '/' + file) else 0),
            expected_files
        )
        progress: int = int(num_existing_files / num_expected_files) * 100

        global analyzer_status, analyzer_result
        runtime_info['progress'] = progress
        if progress == 100:
            print('Analyzer task finished')
            runtime_info['finished'] = True
            analyzer_status['status'] = 'IDLE'
            analyzer_result = get_analyzer_result()
            print('Runtime info', runtime_info)
        sleep(POLLING_PERIOD)


def get_analyzer_result() -> list:
    """
    Returns the result of latest spark job. The result of spark job is a list of paths
    of produced artifacts
    :return:
    """
    workdir = os.getenv('SIMBAD_ANALYZER_WORKDIR')
    return list(map(lambda file: (workdir + '/' + file, os.path.getsize(workdir + '/' + file)), expected_files))


@app.route('/api/analyzer/start', methods=['POST'])
def start():
    global analyzer_status
    if analyzer_status['finished'] is True:
        return 402

    request_data: dict = request_to_json(request)
    path: str = request_data['path']
    start_analyzer(path)
    return 202


@app.route('/api/analyzer/status')
def status():
    return 202, jsonify(analyzer_status)


@app.route('/api/analyzer/runtime')
def runtime():
    return 202, jsonify(runtime_info)


@app.route('/api/analyzer/result')
def result():
    return 202, jsonify(result)


def request_to_json(req) -> dict:
    return json.loads(req.data.decode('utf8'))


def start_server():
    p = argparse.ArgumentParser()
    p.add_argument('--host', dest='host', default='0.0.0.0')
    p.add_argument('--port', dest='port', type=int, default=5000)
    p.add_argument('--debug', dest='debug', action='store_true')
    args = p.parse_args()
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    start_server()
