FROM python:3.7

ARG APP_VERSION

ENV QAWEBAPI_APP_VERSION=$APP_VERSION
ENV APP_HOME=/qa-webapi
ENV APP_CFG=uwsgi.ini
ENV APP_PORT=8080

COPY src $APP_HOME
COPY deployment/$APP_CFG $APP_HOME/
COPY deployment/start.sh $APP_HOME/

RUN apt-get update && \
    apt-get install -y python3-dev build-essential

WORKDIR $APP_HOME

RUN pip install -r requirements.txt
RUN pip install uwsgi

EXPOSE $APP_PORT

RUN chmod +x ./start.sh
CMD ["./start.sh"]