import os
import uuid
import json

from flask import Flask, request
from werkzeug.utils import secure_filename
import pystache

import process_logs


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
FILE_DB = "/tmp/grass-collector/"


app = Flask(__name__)


@app.route('/')
def index():
    log_data = process_logs.process_logs(FILE_DB)
    return pystache.render(
        open(os.path.join(SCRIPT_DIR, "main-page.mustache")).read(),
        log_data)

@app.route("/upload", methods=["POST"])
def upload():
    player_name = request.form["player"]
    if player_name is None or player_name.strip() == "":
        return "Error: No player name given"

    log_files = request.files.getlist("logs")
    if len(log_files) == 0 or any(f.filename.strip() == "" for f in log_files):
        return "Error: No log files given"

    for f in log_files:
        dir_path = os.path.join(
            FILE_DB,
            secure_filename(player_name))
        os.makedirs(dir_path, exist_ok=True)
        f.save(os.path.join(
            dir_path,
            secure_filename(f.filename + "-" + uuid.uuid4().hex)))

    return "Success! <a href='/'>Return to homepage</a>"

@app.route("/json", methods=["GET"])
def getjson():
    log_data = process_logs.process_logs(FILE_DB)
    return json.dumps(log_data["grassRaw"])
