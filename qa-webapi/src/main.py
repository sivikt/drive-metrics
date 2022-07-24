from config.config import CONFIGURATION

import logging
from flask import Flask
from flask import request

from qa_rest_api import mod as qa_rest_api_mod
from utils import http


logger = logging.getLogger(__name__)


app = Flask(__name__, static_folder='static')
app.config.from_object(__name__)
app.config.update(CONFIGURATION)


#logger.info('USE CONFIG %s', app.config)


app.register_blueprint(qa_rest_api_mod, url_prefix='/')


@app.errorhandler(404)
def handle_error(e):
    return http.response_error_404('not_found', 'Requested resource not found')


@app.errorhandler(500)
def handle_error(e):
    logger.exception('ISE occurred')
    return http.response_error_500('ise', 'Something went wrong. Contact an administrator')


@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    if request.method == 'OPTIONS':
        response.headers['Access-Control-Allow-Methods'] = 'DELETE, GET, POST, PUT'
        headers = request.headers.get('Access-Control-Request-Headers')
        if headers:
            response.headers['Access-Control-Allow-Headers'] = headers
    return response


def run():
    app.run(host=app.config.get('HOST'), port=app.config.get('SERVER_PORT'), debug=app.config.get('DEBUG'))


if __name__ == '__main__':
    run()
