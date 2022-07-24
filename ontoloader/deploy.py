import os
import argparse


parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('--build_ver', type=str, default='SNAPSHOT-0.0.1',
                   help='container build version')
parser.add_argument('--is_fresh_update', type=bool, default=False,
                   help='is_fresh_update')
parser.add_argument('--profile', type=str, default='test',
                   help='profile')

args = parser.parse_args()


NAMESPACE = f'ingress-{args.profile}'
K8S_DIR = 'deployment/k8s'
SERVICE_NAME='ontoloader'
SERVICE_VER=f'{args.build_ver}'
ACR_REPOSITORY='dm.azurecr.io'


print(f"Build version '{args.build_ver}'")
print(f"Build profile '{args.profile}'")
print(f"Do fresh update '{args.is_fresh_update}'")
print(f"Use K8S namespace '{NAMESPACE}'")


os.system('az login')
#os.system('az aks install-cli')
os.system('az aks get-credentials --resource-group dms --name akscluster')
os.system('az acr login --name dmsacr')

os.system(
    (f'docker build . -f deployment/Dockerfile '
     f' --build-arg APP_VERSION="{args.build_ver}" '
     f' --build-arg HOST_SSH_PRIVATE_KEY="$(cat ~/.ssh/dmonto_rsa)" '
     f' --build-arg DB_FRESH_UPDATE="{args.is_fresh_update}" '
     f'-t {SERVICE_NAME}')
)
os.system(f'docker tag {SERVICE_NAME} {ACR_REPOSITORY}/{SERVICE_NAME}:{SERVICE_VER}')
os.system(f'docker push {ACR_REPOSITORY}/{SERVICE_NAME}:{SERVICE_VER}')

os.system(
    (f'python3 {K8S_DIR}/ontoloader-{args.profile}-config.yaml.py {args.build_ver} '
     f'| kubectl delete -n {NAMESPACE} -f -')
)
os.system(f'python3 {K8S_DIR}/ontoloader-{args.profile}-config.yaml.py {args.build_ver} | kubectl apply -n {NAMESPACE} -f -')

os.system(
    (f'python3 {K8S_DIR}/ontoloader-{args.profile}.job.yaml.py {args.build_ver} '
     f'| kubectl delete -n {NAMESPACE} -f -')
)
os.system(
    (f'python3 {K8S_DIR}/ontoloader-{args.profile}.job.yaml.py {args.build_ver} '
     f'| kubectl apply -n {NAMESPACE} -f -')
)
