import sys

version = sys.argv[1]

yaml = f"""
apiVersion: apps/v1beta1
kind: Deployment
metadata:
  name: ontologyqa-dpl
  namespace: ingress-test
spec:
  replicas: 1
  strategy:
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 1
  minReadySeconds: 5
  template:
    metadata:
      labels:
        app: ontologyqa
    spec:
      containers:
      - name: ontologyqa
        env:
          - name: GOOGLE_APPLICATION_CREDENTIALS
            value: /app/gcp_key.json
          - name: qa-webapi_app_config
            value: /app/app_config.yaml
          - name: qa-webapi_log_config
            value: /app/log_config.yaml
        image: dm.azurecr.io/ontologyqa:{version}
        ports:
        - containerPort: 8080
          name: ontologyqa-api
          protocol: TCP
        volumeMounts:
          - name: config-volume
            mountPath: /app
      volumes:
        - name: config-volume
          configMap:
            name: ontologyqa-test-app-config
"""


if __name__ == '__main__':
    print(yaml)
