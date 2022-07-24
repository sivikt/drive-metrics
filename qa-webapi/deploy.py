import os
import argparse


parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('--build_ver', type=str, default='SNAPSHOT-0.0.1',
                   help='container build version')
parser.add_argument('--profile', type=str, default='test',
                   help='profile')

args = parser.parse_args()


NAMESPACE = f'ingress-{args.profile}'
K8S_DIR = 'deployment/k8s'
SERVICE_NAME='ontologyqa'
SERVICE_VER=f'{args.build_ver}'
ACR_REPOSITORY='dm.azurecr.io'


print(f"Build version '{args.build_ver}'")
print(f"Build profile '{args.profile}'")
print(f"Use K8S namespace '{NAMESPACE}'")


os.system('az login')
os.system('az aks install-cli')
os.system('az aks get-credentials --resource-group dms --name akscluster')
os.system('az acr login --name dmsacr')

os.system(f'python3 -c "import nltk; nltk.download(\'punkt\', download_dir=\'./src/nltk_data/\')"')

os.system(f'docker build . -f deployment/Dockerfile --build-arg APP_VERSION="{args.build_ver}" -t {SERVICE_NAME}')
os.system(f'docker tag {SERVICE_NAME} {ACR_REPOSITORY}/{SERVICE_NAME}:{SERVICE_VER}')
os.system(f'docker push {ACR_REPOSITORY}/{SERVICE_NAME}:{SERVICE_VER}')

os.system(f'kubectl delete -n {NAMESPACE} -f {K8S_DIR}/ontologyqa-{args.profile}-config.yaml')
os.system(f'kubectl apply -n {NAMESPACE} -f {K8S_DIR}/ontologyqa-{args.profile}-config.yaml')

os.system(f'python3 {K8S_DIR}/ontologyqa-{args.profile}.yaml.py {args.build_ver} | kubectl delete -n {NAMESPACE} -f -')
os.system(f'python3 {K8S_DIR}/ontologyqa-{args.profile}.yaml.py {args.build_ver} | kubectl apply -n {NAMESPACE} -f -')
