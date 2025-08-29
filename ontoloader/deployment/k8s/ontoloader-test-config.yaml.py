import sys

VERSION = sys.argv[1]
REPO_NAME = 'test_repo'

yaml = f"""
apiVersion: v1
kind: ConfigMap
metadata:
  name: ontoloader-test-app-config
  namespace: ingress-test
data:
  app_config.yaml: |
    NEO4J_ENDPOINT: 'bolt://neo4j:cetyW2!@10.240.0.9:7687'
    GRAPHDB:
        FRESH_UPDATE: true
        ENDPOINT: 'https://10.10.10.231:7200'
        USERNAME: 'admin'
        PASSWORD: ''
        REPOSITORY_ID: '{REPO_NAME}'
        MAIN_TRIPS_DATA_GRAPH: ''
    BATCH_UPDATE_SIZE: 20

  log_config.yaml: |
    version: 1
    disable_existing_loggers: False
    formatters:
      simple:
        format: "%(asctime)s %(levelname)-8s - [%(name)s.%(funcName)s:%(lineno)d] %(message)s"
        datefmt: "%d-%b-%Y %H:%M:%S:%z"

    handlers:
      console:
        class: logging.StreamHandler
        level: DEBUG
        formatter: simple
        stream: ext://sys.stdout

    loggers:
      urllib3.connectionpool:
        level: INFO
        propogate: yes

      neobolt:
        level: INFO
        propogate: yes

    root:
      level: DEBUG
      handlers: [console]

  repo_config.ttl: |
    #
    # RDF4J configuration template for a GraphDB Free repository
    #
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>.
    @prefix rep: <http://www.openrdf.org/config/repository#>.
    @prefix sr: <http://www.openrdf.org/config/repository/sail#>.
    @prefix sail: <http://www.openrdf.org/config/sail#>.
    @prefix owlim: <http://www.ontotext.com/trree/owlim#>.

    [] a rep:Repository ;
        rep:repositoryID "{REPO_NAME}" ;
        rdfs:label "{REPO_NAME}_{VERSION}" ;
        rep:repositoryImpl [
            rep:repositoryType "graphdb:FreeSailRepository" ;
            sr:sailImpl [
                sail:sailType "graphdb:FreeSail" ;

                owlim:base-URL "http://example.org/owlim#" ;
                owlim:defaultNS "" ;
                owlim:entity-index-size "10000000" ;
                owlim:entity-id-size  "32" ;
                owlim:imports "" ;
            	owlim:repository-type "file-repository" ;
                owlim:ruleset "owl-max" ;
                owlim:storage-folder "storage" ;

                owlim:enable-context-index "true" ;

                owlim:enablePredicateList "true" ;

                owlim:in-memory-literal-properties "true" ;
                owlim:enable-literal-index "true" ;

                owlim:check-for-inconsistencies "true" ;
                owlim:disable-sameAs  "false" ;
                owlim:query-timeout  "0" ;
                owlim:query-limit-results  "0" ;
                owlim:throw-QueryEvaluationException-on-timeout "true" ;
                owlim:read-only "false" ;
            ]
        ].
"""


if __name__ == '__main__':
    print(yaml)
