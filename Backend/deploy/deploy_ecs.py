"""Deploy do O.R.A.C.U.L.O. (API + dashboard) no ECS Fargate com autoscaling (ECS Express Mode).

Por que assim (conta do Workshop Studio, verificado em 2026-09-26): o papel do participante NÃO
pode dar push no ECR, criar security group, lançar EC2, usar CloudFront/ALB/App Runner/Lambda-role
diretamente. Mas pode: S3, ECS, criar as PRÓPRIAS roles (o Deny cobre só WS*/cdk-*/CodeEditor) e
passá-las ao ECS. O ECS Express Mode cria Fargate + ALB (HTTPS) + security groups + autoscaling
usando a role de infraestrutura que passamos — tudo dentro do que o workshop permite.

Sem ECR: o container é a imagem PÚBLICA python:3.11-slim (public.ecr.aws, sem limite de pull) e,
ao subir, baixa do S3 o pacote (código + dependências Linux + build do dashboard) usando a task
role (por isso nada expira: novas tasks do autoscaling também conseguem subir). Em uma conta sem
essas restrições, prefira a imagem Docker ao lado (Backend/deploy/Dockerfile) + ECR.

Como rodar (de Backend/, depois de `npm run build` em Frontend/oraculo-dashboard):

    # credenciais temporárias do workshop no ambiente (nunca em arquivo do repositório):
    #   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN, AWS_DEFAULT_REGION
    pip install boto3
    python deploy/deploy_ecs.py                 # empacota, sobe e imprime a URL
    python deploy/deploy_ecs.py --so-empacotar  # só monta o pacote (sem AWS)

Idempotente: reexecutar atualiza o pacote no S3 e reinicia o serviço. Tempo: 3-8 min.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent          # Backend/
REPO = BACKEND.parent
DIST = REPO / "Frontend" / "oraculo-dashboard" / "dist"   # build do Vite (servido pela API)
REQ_API = BACKEND / "deploy" / "requirements-api.txt"    # fonte única das deps de runtime (DRY)

SERVICO = "oraculo"
IMAGEM = "public.ecr.aws/docker/library/python:3.11-slim"  # mesma versão do pyproject (>=3.11,<3.13)
PORTA = 8000

# Dados que NÃO estão no git (.gitignore): banco publicado pelo run_heavywork.py, saídas da visão
# e cache do protótipo. Vão para o S3 num zip só; o deploy local os envia e o CI (GitHub Actions),
# que só tem o código, os baixa de lá. Para atualizar os dados na demo: rodar o deploy LOCAL.
DADOS = ["oraculo.db", "output", "data/oraculo_cache"]
CHAVE_DADOS = "dados/dados.zip"

# O que a API lê em runtime (mesma lista branca do Dockerfile.dockerignore). Como não há limite de
# 250 MB aqui (isso era do Lambda), o cache real do protótipo entra: a demo não depende da rede do ONS.
COPIAR = ["main.py", "alembic.ini", "config", "migrations", "src", "oraculo", *DADOS]

# Roles próprias (o workshop só bloqueia anexar policy a roles WS*/cdk-*/CodeEditor).
POLICY_EXEC = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
POLICY_INFRA = "arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices"

# Comando do container: baixa o pacote do S3 (boto3 + credenciais da task role), extrai em /app e
# sobe o uvicorn. Backend/ como diretório de trabalho e /app no PYTHONPATH (dependências na raiz).
BOOT = r"""
pip install -q --no-cache-dir boto3 &&
python - <<'PY'
import os, zipfile, boto3
boto3.client("s3").download_file(os.environ["BUNDLE_BUCKET"], os.environ["BUNDLE_KEY"], "/tmp/b.zip")
zipfile.ZipFile("/tmp/b.zip").extractall("/app")
PY
cd /app/Backend && PYTHONPATH=/app exec python -m uvicorn main:app --host 0.0.0.0 --port 8000
"""


def montar_pacote(destino: Path) -> None:
    """Instala as deps para Linux x86_64 (o Fargate), copia o código e o build do dashboard."""
    if not DIST.exists():
        sys.exit(f"Falta o build do dashboard: rode `npm run build` em {DIST.parent} primeiro.")
    deps = [l.strip() for l in REQ_API.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")]
    # --platform/--only-binary: baixa as rodas do Linux mesmo rodando no Windows.
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "--no-compile", "--target", str(destino),
         "--only-binary=:all:", "--python-version", "3.11", "--implementation", "cp",
         "--platform", "manylinux2014_x86_64", "--platform", "manylinux_2_17_x86_64",
         "--platform", "manylinux_2_28_x86_64", *deps],
        check=True)
    raiz = destino / "Backend"
    for rel in COPIAR:
        origem = BACKEND / rel
        alvo = raiz / rel
        if origem.is_dir():
            shutil.copytree(origem, alvo, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origem, alvo)
    # Mesmo layout do repositório: config/api.yaml aponta dashboard_dist para ../Frontend/...
    shutil.copytree(DIST, destino / "Frontend" / "oraculo-dashboard" / "dist")
    # Poda: testes e caches embutidos nas rodas (scipy/numpy) pesam dezenas de MB e nunca rodam.
    for pasta in list(destino.rglob("tests")) + list(destino.rglob("__pycache__")):
        if pasta.is_dir() and "Backend" not in pasta.parts:
            shutil.rmtree(pasta, ignore_errors=True)


def zipar(pasta: Path, saida: Path) -> None:
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in pasta.rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(pasta).as_posix())


def _bucket(s3, conta: str, regiao: str) -> str:
    """Cria (ou reaproveita) o bucket do deploy e devolve o nome."""
    from botocore.exceptions import ClientError
    bucket = f"oraculo-deploy-{conta}-{regiao}"
    try:
        s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": regiao})
    except ClientError as e:
        if e.response["Error"]["Code"] not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            raise
    return bucket


def sincronizar_dados(s3, bucket: str) -> None:
    """Máquina com o banco (deploy local): envia os dados ao S3. Sem o banco (CI): baixa e extrai."""
    if (BACKEND / "oraculo.db").exists():
        tmp = Path(tempfile.gettempdir()) / "oraculo_dados.zip"
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for rel in DADOS:
                origem = BACKEND / rel
                arquivos = [f for f in origem.rglob("*") if f.is_file()] if origem.is_dir() else [origem]
                for f in arquivos:
                    z.write(f, f.relative_to(BACKEND).as_posix())
        print(f"enviando dados ({tmp.stat().st_size / 1024 / 1024:.0f} MB) para s3://{bucket}/{CHAVE_DADOS}")
        s3.upload_file(str(tmp), bucket, CHAVE_DADOS)
        return
    print(f"oraculo.db não está no checkout: baixando dados de s3://{bucket}/{CHAVE_DADOS}")
    tmp = Path(tempfile.gettempdir()) / "oraculo_dados.zip"
    s3.download_file(bucket, CHAVE_DADOS, str(tmp))  # falha clara se ninguém fez o deploy local antes
    zipfile.ZipFile(tmp).extractall(BACKEND)


def _role(iam, nome: str, servico: str, policy_arn: str | None = None, inline: dict | None = None) -> str:
    """Cria (ou reaproveita) uma role confiável para `servico` e anexa a policy. Devolve o ARN."""
    from botocore.exceptions import ClientError
    trust = {"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow", "Principal": {"Service": servico}, "Action": "sts:AssumeRole"}]}
    try:
        arn = iam.create_role(RoleName=nome, AssumeRolePolicyDocument=json.dumps(trust))["Role"]["Arn"]
    except ClientError as e:
        if e.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        arn = iam.get_role(RoleName=nome)["Role"]["Arn"]
    if policy_arn:
        iam.attach_role_policy(RoleName=nome, PolicyArn=policy_arn)
    if inline:
        iam.put_role_policy(RoleName=nome, PolicyName="inline", PolicyDocument=json.dumps(inline))
    return arn


def publicar(zip_path: Path, regiao: str, min_tasks: int, max_tasks: int, s3, bucket: str, conta: str) -> None:
    import boto3
    from botocore.exceptions import ClientError

    iam = boto3.client("iam", region_name=regiao)
    ecs = boto3.client("ecs", region_name=regiao)
    logs = boto3.client("logs", region_name=regiao)

    chave = f"{SERVICO}.zip"
    print(f"enviando {zip_path.stat().st_size / 1024 / 1024:.0f} MB para s3://{bucket}/{chave} ...")
    s3.upload_file(str(zip_path), bucket, chave)

    # Task role: só lê o pacote (escopo mínimo). Execution role: puxa imagem/escreve logs.
    task_role = _role(iam, "oraculo-task-role", "ecs-tasks.amazonaws.com", inline={
        "Version": "2012-10-17", "Statement": [{
            "Effect": "Allow", "Action": "s3:GetObject", "Resource": f"arn:aws:s3:::{bucket}/{chave}"}]})
    exec_role = _role(iam, "oraculo-exec-role", "ecs-tasks.amazonaws.com", POLICY_EXEC)
    infra_role = _role(iam, "oraculo-infra-role", "ecs.amazonaws.com", POLICY_INFRA)
    grupo = f"/ecs/{SERVICO}"
    try:
        logs.create_log_group(logGroupName=grupo)
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceAlreadyExistsException":
            raise
    time.sleep(10)  # propagação do IAM antes de o ECS assumir as roles

    container = {
        "image": IMAGEM, "containerPort": PORTA,
        "command": ["sh", "-c", BOOT],
        "environment": [{"name": "BUNDLE_BUCKET", "value": bucket}, {"name": "BUNDLE_KEY", "value": chave},
                        {"name": "AWS_DEFAULT_REGION", "value": regiao},
                        {"name": "PYTHONUNBUFFERED", "value": "1"},
                        # único diretório gravável e barato para o cache do protótipo
                        {"name": "ORACULO_CACHE", "value": "/tmp/oraculo_cache"}],
        "awsLogsConfiguration": {"logGroup": grupo, "logStreamPrefix": "api"},
    }
    args = dict(
        serviceName=SERVICO, executionRoleArn=exec_role, infrastructureRoleArn=infra_role,
        taskRoleArn=task_role, primaryContainer=container, healthCheckPath="/api-docs",
        cpu="1024", memory="2048",
        # Autoscaling: mantém CPU média em ~60%; sobe até max_tasks sob carga e volta a min_tasks.
        scalingTarget={"minTaskCount": min_tasks, "maxTaskCount": max_tasks,
                       "autoScalingMetric": "AVERAGE_CPU", "autoScalingTargetValue": 60})
    arn = f"arn:aws:ecs:{regiao}:{conta}:service/default/{SERVICO}"
    # Existe? (describe é a checagem explícita; não dependo do texto do erro de create)
    try:
        existe = ecs.describe_express_gateway_service(serviceArn=arn)["service"]["status"]["statusCode"] == "ACTIVE"
    except ClientError:
        existe = False
    if not existe:
        r = ecs.create_express_gateway_service(**args)
    else:
        # O update não aceita nome nem role de infraestrutura (fixos na criação).
        for k in ("serviceName", "infrastructureRoleArn"):
            args.pop(k)
        r = ecs.update_express_gateway_service(serviceArn=arn, **args)
        # A configuração pode não ter mudado (só o pacote no S3), e nesse caso o ECS não faria
        # nenhum deployment: força a troca das tasks para elas baixarem o pacote novo.
        ecs.update_service(cluster="default", service=SERVICO, forceNewDeployment=True)
    print(json.dumps(r, default=str, indent=2)[:1500])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--so-empacotar", action="store_true", help="monta o pacote e para (não usa a AWS)")
    ap.add_argument("--saida", type=Path, default=Path(tempfile.gettempdir()) / "oraculo_ecs",
                    help="pasta de trabalho (curta: o Windows tem limite de caminho)")
    ap.add_argument("--regiao", default="us-west-2")
    ap.add_argument("--min-tasks", type=int, default=1)
    ap.add_argument("--max-tasks", type=int, default=4)
    args = ap.parse_args()

    s3 = bucket = conta = None
    if not args.so_empacotar:
        import boto3
        conta = boto3.client("sts", region_name=args.regiao).get_caller_identity()["Account"]
        s3 = boto3.client("s3", region_name=args.regiao)
        bucket = _bucket(s3, conta, args.regiao)
        sincronizar_dados(s3, bucket)  # antes de empacotar: no CI é daqui que vem o banco

    if args.saida.exists():
        shutil.rmtree(args.saida)
    pacote = args.saida / "pacote"
    montar_pacote(pacote)
    zip_path = args.saida / f"{SERVICO}.zip"
    zipar(pacote, zip_path)
    print(f"zip: {zip_path} ({zip_path.stat().st_size / 1024 / 1024:.0f} MB)")
    if not args.so_empacotar:
        publicar(zip_path, args.regiao, args.min_tasks, args.max_tasks, s3, bucket, conta)


if __name__ == "__main__":
    main()
