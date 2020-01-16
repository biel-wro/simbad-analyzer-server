import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
from time import sleep
from typing import List
from logging.config import dictConfig

from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)


dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'formatter': 'default'
    }},
    'root': {
        'level': 'DEBUG',
        'handlers': ['wsgi']
    }
})

app = Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True

logging.basicConfig(filename='analyzer.log', level=logging.ERROR)

SIMBAD_ANALYZER_RUN_SCRIPT_PATH = os.getenv('SIMBAD_ANALYZER_RUN_SCRIPT_PATH', './scripts/mock/run.sh')
SIMBAD_ANALYZER_STATUS_SCRIPT_PATH = os.getenv('SIMBAD_ANALYZER_STATUS_SCRIPT_PATH', './scripts/mock/status.sh')
SIMBAD_ANALYZER_RESULT_SCRIPT_PATH = os.getenv('SIMBAD_ANALYZER_RESULT_SCRIPT_PATH', './scripts/mock/result.sh')
POLLING_PERIOD = 3

runtime_info: dict = {'finished': False, "progress": 0}
analyzer_status: dict = {"status": "IDLE"}
analyzer_result: list = []

spark_out = ""

expected_files: List[str] = [
    "time_points.parquet",
    "large_clones.parquet",
    "clone_snapshots.parquet",
    "final_snapshot.csv",
    "clone_stats.parquet",
    "clone_stats_scalars.parquet",
    "large_muller_order.parquet",
    "muller_data.parquet",
    "final_mutation_freq.parquet",
    "clone_counts.parquet",
    "large_final_mutations.parquet",
    "chronicles.parquet",
    "lineages.parquet",
    "major_stats.parquet",
    "major_stats_scalars.parquet",
    "muller_data.parquet",
    "noise_stats.parquet",
    "noise_stats_scalars.parquet",
    "time_points.parquet",
    "final_snapshot.csv",
    "histogram_birthEfficiency.csv",
    "histogram_birthResistance.csv",
    "histogram_lifespanEfficiency.csv",
    "histogram_lifespanEfficiency.csv",
    "histogram_lifespanEfficiency.csv",
    "histogram_lifespanResistance.csv",
    "histogram_successEfficiency.csv",
    "histogram_successResistance.csv",
    "major_histogram_birthEfficiency.csv",
    "major_histogram_birthResistance.csv",
    "major_histogram_lifespanEfficiency.csv",
    "major_histogram_lifespanResistance.csv",
    "major_histogram_successEfficiency.csv",
    "major_histogram_successResistance.csv",
    "noise_histogram_birthEfficiency.csv",
    "noise_histogram_birthResistance.csv",
    "noise_histogram_lifespanEfficiency.csv",
    "noise_histogram_lifespanResistance.csv",
    "noise_histogram_successEfficiency.csv",
    "noise_histogram_successResistance.csv"
]


def start_analyzer(path: str) -> None:
    """
    Starts analyzer job and spawns thread that updates
    analyzer runtime info. The workdir for simulation process is the same as
    CLI output file dir
    :param path: the path to CLI output file
    :return:
    """
    workdir = os.path.dirname(path)
    global spark_out
    spark_out = workdir + "/output_data"
    stream_dir = workdir + "/stream.parquet/"
    spark_out_dir = workdir + "/output_data"
    os.environ["SIMBAD_ANALYZER_WORKDIR"] = workdir + "/output_data"

    spark_warehouse_dir = "/usr/analyzer-server/app/spark-warehouse"
    checkpoints_dir = "/usr/analyzer-server/app/checkpoints"
    out_checkpoints_dir = spark_out + "/checkpoints"

    if os.path.exists(spark_warehouse_dir) and os.path.isdir(spark_warehouse_dir):
        sys.stderr.write("Removing warehouse...\n")
        shutil.rmtree(spark_warehouse_dir)
    if os.path.exists(checkpoints_dir) and os.path.isdir(checkpoints_dir):
        sys.stderr.write("Removing checkpoints...\n")
        shutil.rmtree(checkpoints_dir)
    if os.path.exists(out_checkpoints_dir) and os.path.isdir(out_checkpoints_dir):
        sys.stderr.write("Removing output_data/checkpoints/...\n")
        shutil.rmtree(out_checkpoints_dir)

    reader_cmd = "" \
                 "spark-submit" \
                 " --master local " \
                 "--class analyzer.StreamReader " \
                 "/jar/analyzer.jar {} {}" \
        .format(path, stream_dir)
    reader_process = subprocess.Popen(reader_cmd, shell=True)
    reader_process.wait()
    analyzer_cmd = "spark-submit" \
                   " --master local " \
                   "--class analyzer.Analyzer /jar/analyzer.jar {} {}" \
        .format(stream_dir, spark_out_dir)
    subprocess.Popen(analyzer_cmd, shell=True)
    thread = threading.Thread(target=update_runtime_info)
    thread.daemon = True
    thread.start()
    return


def update_runtime_info() -> None:
    """
    Periodically update runtime info of current analyzer job
    :return:
    """
    global analyzer_status, analyzer_result, runtime_info, spark_out
    while runtime_info['finished'] is not True:
        num_expected_files: int = len(expected_files)

        num_existing_files: int = 0
        for file in expected_files:
            if os.path.exists(spark_out + "/" + file):
                num_existing_files += 1

        progress: int = int((num_existing_files / num_expected_files) * 100)
        runtime_info['progress'] = progress

        if progress == 100:
            print('Analyzer task finished')
            runtime_info['finished'] = True
            analyzer_status['status'] = 'IDLE'
            analyzer_result = get_analyzer_result()
            print('Runtime info', runtime_info)

        sleep(POLLING_PERIOD)

    out_checkpoints_dir = spark_out + "/checkpoints"

    if os.path.exists(out_checkpoints_dir) and os.path.isdir(out_checkpoints_dir):
        sys.stderr.write("Removing output_data/checkpoints/...\n")
        shutil.rmtree(out_checkpoints_dir)

    return


def get_analyzer_result() -> list:
    """
    Returns the result of latest spark job. The result of spark job is a list of paths
    of produced artifacts
    :return:
    """
    return list(map(lambda file: spark_out + "/" + file, expected_files))


@app.route('/api/analyzer/start', methods=['POST'])
def start():
    global analyzer_status, analyzer_result, runtime_info
    if analyzer_status['status'] is 'BUSY':
        app.logger.info('Start request failed - analyzer is BUSY')
        return {"status": "failed"}, 402

    print(request.data)
    request_data: dict = request_to_json(request)
    path: str = request_data['path']
    analyzer_status['status'] = 'BUSY'
    analyzer_result = []
    runtime_info['progress'] = 0
    runtime_info['finished'] = False

    start_analyzer(path)
    return "OK", 202


@app.route('/api/analyzer/status')
def status():
    return jsonify(analyzer_status)


@app.route('/api/analyzer/runtime')
def runtime():
    return jsonify(runtime_info)


@app.route('/api/analyzer/result')
def result():
    return jsonify(analyzer_result)


@app.route('/', methods=['POST'])
def test():
    request_data: dict = request_to_json(request)
    print(request_data)
    return jsonify(analyzer_result)


def request_to_json(req) -> dict:
    return json.loads(req.data.decode('utf8'))


def start_server():
    p = argparse.ArgumentParser()
    p.add_argument('--host', dest='host', default='0.0.0.0')
    p.add_argument('--port', dest='port', type=int, default=5000)
    p.add_argument('--debug', dest='debug', action='store_true')
    args = p.parse_args()
    app.run(host=args.host, port=args.port, debug=False)


@app.errorhandler(500)
def internal_error(exception):
    app.logger.error(exception)
    return 500


if __name__ == '__main__':
    start_server()
