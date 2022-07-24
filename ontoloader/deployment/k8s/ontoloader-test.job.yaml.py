import sys

VERSION = sys.argv[1]

yaml = f"""
apiVersion: batch/v1beta1
kind: CronJob
metadata:
  name: ontoloader-cronjob
  namespace: ingress-test
spec:
  schedule: "*/5 * * * *"
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: Never
          containers:
          - name: ontoloader
            env:
              - name: ONTOLOADER_APP_CONFIG
                value: /app/app_config.yaml
              - name: ONTOLOADER_LOG_CONFIG
                value: /app/log_config.yaml
              - name: ONTOLOADER_REPO_CONFIG
                value: /app/repo_config.ttl
            volumeMounts:
              - name: config-volume
                mountPath: /app
            image: dm.azurecr.io/ontoloader:{VERSION}
          volumes:
            - name: config-volume
              configMap:
                name: ontoloader-test-app-config
          restartPolicy: Never
"""


if __name__ == '__main__':
    print(yaml)
