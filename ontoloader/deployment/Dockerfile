FROM python:3.7-slim-buster

ARG HOST_SSH_PRIVATE_KEY
ARG APP_VERSION
ARG DB_FRESH_UPDATE

ENV ONTOLOADER_DB_FRESH_UPDATE=$DB_FRESH_UPDATE
ENV ONTOLOADER_APP_VERSION=$APP_VERSION
ENV APP_HOME=/ontoloader_home
ENV SSH_HOME=/root/.ssh
ENV SSH_KEY=$SSH_HOME/id_rsa

# Setup ssh
RUN  apt-get -yq update && \
     apt-get -yqq install ssh

RUN mkdir $SSH_HOME
RUN echo "$HOST_SSH_PRIVATE_KEY" >> $SSH_KEY
RUN chmod 600 $SSH_KEY
RUN touch $SSH_HOME/known_hosts
RUN ssh-keyscan bitbucket.org >> $SSH_HOME/known_hosts

# Copy application sources
COPY src $APP_HOME/src

WORKDIR $APP_HOME

# Install dependencies
RUN apt-get install -y git libgeos-dev

WORKDIR src
RUN chmod +x install_deps.sh
RUN ./install_deps.sh

RUN rm $SSH_KEY

# Run application
CMD [ "python", "main.py" ]