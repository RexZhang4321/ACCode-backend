from flask import Flask, request, Response
import Explorer
import Tools
import json
import os
from flask_cors import CORS
import redis
import datetime

app = Flask(__name__)
CORS(app)
red = redis.StrictRedis()


def event_stream(project):
    pubsub = red.pubsub()
    pubsub.subscribe(project)
    for msg in pubsub.listen():
        if type(msg['data']) is not int:
            yield 'data: %s\n\n' % msg['data'].decode()


@app.route("/", methods=['GET'])
def index():
    return "hello world"


@app.route("/explorer/getdir", methods=['GET'])
def get_dir():
    return json.dumps(Explorer.list_directory_recursive('../test-android-hello'))


@app.route("/explorer/project", methods=['GET'])
def get_file():
    baseDir = '../test-android-hello'
    path = request.args.get('path')
    filePath = baseDir + path
    return Explorer.read_file_content(filePath)


@app.route("/tools/build", methods=['GET'])
def build_project():
    projectName = request.args.get('project')
    # Tools.build_project(projectName)
    return 'build issued!'


@app.route('/subscribeServer')
def test_subscribe():
    project = request.args.get('project')
    return Response(event_stream(project), mimetype='text/event-stream')


@app.route('/push', methods=['POST'])
def push_to_client():
    print(request.get_json(), flush=True)
    data = request.get_json()
    red.publish(data['project'], json.dumps(data))
    return json.dumps(data)


@app.route('/tools/buildlog', methods=['GET'])
def get_buildlog():
    buildId = request.args.get('buildId')
    startTime = int(request.args.get('startTime'))
    logEvents = Tools.get_buildlogs(buildId, startTime)
    return json.dumps(logEvents)


@app.route('/test/publish', methods=['GET'])
def test_publish():
    red.publish('test', 'push from server')
    return 'message sent!'


@app.route('/time', methods=['GET'])
def get_time():
    return json.dumps({'time': round(datetime.datetime.utcnow().timestamp() * 1000)})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
