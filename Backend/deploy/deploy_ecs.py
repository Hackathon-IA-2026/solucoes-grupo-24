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
import re
import time
import urllib.request
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
# mmgd_empreendimentos.parquet: tabela real da Triangulação (BDGD x ANEEL, src/spatial/saidas.py);
# sem ela /api/triangulation responde "tabela ainda não gerada" em produção.
# perfis_classe_ctr.csv: formas horárias medidas (ANEEL CTR) da tela Classes de consumo
# (config/perfis_classe.yaml, oraculo/profiles/medidos.py).
DADOS = ["oraculo.db", "output", "data/oraculo_cache",
         "data/processed/mmgd_empreendimentos.parquet", "data/processed/perfis_classe_ctr.csv"]
CHAVE_DADOS = "dados/dados.zip"

# O que a API lê em runtime (mesma lista branca do Dockerfile.dockerignore): código (do checkout) +
# DADOS (da pasta montada por sincronizar_dados). Como não há limite de 250 MB aqui (isso era do
# Lambda), o cache real do protótipo entra: a demo não depende da rede do ONS.
CODIGO = ["main.py", "alembic.ini", "config", "migrations", "src", "oraculo"]

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


def montar_pacote(destino: Path, base_dados: Path) -> None:
    """Instala as deps para Linux x86_64 (o Fargate), copia o código, os DADOS (de `base_dados`,
    ver sincronizar_dados) e o build do dashboard."""
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
    # Dado ausente = página quebrada em produção. No CI isso acontece quando o dados.zip do S3 é de
    # antes de um item novo em DADOS: falha aqui, com a instrução, em vez de publicar sem ele.
    itens = [(BACKEND / rel, rel) for rel in CODIGO] + [(base_dados / rel, rel) for rel in DADOS]
    faltando = [rel for origem, rel in itens if not origem.exists()]
    if faltando:
        sys.exit(f"Faltam no pacote: {', '.join(faltando)}. Rode o deploy LOCAL (máquina com os dados, "
                 f"`python deploy/deploy_ecs.py` em Backend/) para reenviar dados/dados.zip ao S3.")
    for origem, rel in itens:
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


def sincronizar_dados(s3, bucket: str, pasta: Path) -> Path:
    """Monta em `pasta` os DADOS que vão para produção e devolve essa pasta.

    Sempre parte do dados.zip que já está no S3 (o que produção serve hoje). Na máquina com o banco
    (deploy local), os arquivos locais de DADOS SOBRESCREVEM os do S3 e o resultado volta para o S3.
    Decisão: MESCLAR, não substituir. Cada pessoa do time gera partes diferentes (uma tem a visão
    computacional em output/, outra o banco novo); substituir fazia o deploy de quem não tem uma
    das partes apagá-la de produção. Custo: arquivo apagado localmente continua no S3 (remova à mão).
    Sem o banco (CI): só baixa e extrai.
    """
    from botocore.exceptions import ClientError
    pasta.mkdir(parents=True, exist_ok=True)
    tmp = pasta.parent / "oraculo_dados.zip"
    try:
        s3.download_file(bucket, CHAVE_DADOS, str(tmp))
        zipfile.ZipFile(tmp).extractall(pasta)
        print(f"dados de produção (s3://{bucket}/{CHAVE_DADOS}) extraídos como base")
    except ClientError as e:
        if not (BACKEND / "oraculo.db").exists():
            raise  # CI sem dados no S3: falha clara, alguém precisa fazer o deploy local antes
        print(f"sem dados no S3 ainda ({e.response['Error']['Code']}): só os locais")
    if not (BACKEND / "oraculo.db").exists():
        return pasta
    for rel in DADOS:
        origem = BACKEND / rel
        if not origem.exists():
            print(f"  aviso: {rel} não existe nesta máquina; mantém a versão do S3 (se houver)")
            continue
        arquivos = [f for f in origem.rglob("*") if f.is_file()] if origem.is_dir() else [origem]
        for f in arquivos:
            alvo = pasta / f.relative_to(BACKEND)
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, alvo)
    zipar(pasta, tmp)
    print(f"enviando dados ({tmp.stat().st_size / 1024 / 1024:.0f} MB) para s3://{bucket}/{CHAVE_DADOS}")
    s3.upload_file(str(tmp), bucket, CHAVE_DADOS)
    return pasta


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


def _entrada_do_dashboard(html: str) -> str | None:
    """Nome do bundle de entrada do Vite (assets/index-<hash>.js): muda a cada build diferente."""
    m = re.search(r"assets/index-[^\"']+\.js", html)
    return m.group(0) if m else None


def garantir_versao_no_ar(regiao: str, conta: str, tentativas: int = 3, espera_max: int = 900) -> str:
    """Só dá o deploy por bom quando o site serve o build NOVO do dashboard. Devolve a URL.

    Decisão: 200 em /api-docs não prova nada — o ECS Express REVERTE sozinho o deployment quando o
    alarme de erros (RollbackAlarm: >1% de 4xx/5xx, sensível com pouco tráfego) dispara, e a versão
    antiga continua respondendo 200. Por isso comparo o hash do bundle servido com o do dist local e,
    se o ECS reverteu, forço um novo deployment (até `tentativas`).
    """
    import boto3
    ecs = boto3.client("ecs", region_name=regiao)
    arn = f"arn:aws:ecs:{regiao}:{conta}:service/default/{SERVICO}"
    host = ecs.describe_express_gateway_service(serviceArn=arn)["service"]["activeConfigurations"][0][
        "ingressPaths"][0]["endpoint"]
    url = f"https://{host}"
    esperado = _entrada_do_dashboard((DIST / "index.html").read_text(encoding="utf-8"))
    for tentativa in range(1, tentativas + 1):
        limite = time.time() + espera_max
        while time.time() < limite:
            try:
                no_ar = _entrada_do_dashboard(urllib.request.urlopen(url, timeout=15).read().decode("utf-8", "replace"))
            except Exception as e:  # 503 enquanto a task nova sobe é esperado
                no_ar = None
                print(f"  aguardando ({type(e).__name__})")
            if no_ar == esperado:
                print(f"versão nova no ar ({esperado}): {url}")
                return url
            try:
                deps = ecs.describe_services(cluster="default", services=[SERVICO])["services"][0]["deployments"]
            except Exception as e:  # falha passageira de rede/DNS: tenta de novo em vez de derrubar o deploy
                print(f"  não consegui consultar o ECS ({type(e).__name__}); tentando de novo")
                time.sleep(20)
                continue
            if len(deps) == 1 and deps[0]["rolloutState"] == "COMPLETED":
                break  # rollout terminou e o site ainda serve outra versão => foi revertido
            time.sleep(20)
        print(f"tentativa {tentativa}/{tentativas}: o ECS terminou sem a versão nova (rollback?); reimplantando")
        ecs.update_service(cluster="default", service=SERVICO, forceNewDeployment=True)
    sys.exit(f"a versão nova ({esperado}) não ficou no ar depois de {tentativas} tentativas")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--so-empacotar", action="store_true", help="monta o pacote e para (não usa a AWS)")
    ap.add_argument("--saida", type=Path, default=Path(tempfile.gettempdir()) / "oraculo_ecs",
                    help="pasta de trabalho (curta: o Windows tem limite de caminho)")
    ap.add_argument("--regiao", default="us-west-2")
    ap.add_argument("--min-tasks", type=int, default=1)
    ap.add_argument("--max-tasks", type=int, default=4)
    args = ap.parse_args()

    if args.saida.exists():
        shutil.rmtree(args.saida)
    s3 = bucket = conta = None
    base_dados = BACKEND  # --so-empacotar: usa só os dados desta máquina
    if not args.so_empacotar:
        import boto3
        conta = boto3.client("sts", region_name=args.regiao).get_caller_identity()["Account"]
        s3 = boto3.client("s3", region_name=args.regiao)
        bucket = _bucket(s3, conta, args.regiao)
        # Antes de empacotar: no CI é daqui que vem o banco; no local, mescla com o que está no ar.
        base_dados = sincronizar_dados(s3, bucket, args.saida / "dados")

    pacote = args.saida / "pacote"
    montar_pacote(pacote, base_dados)
    zip_path = args.saida / f"{SERVICO}.zip"
    zipar(pacote, zip_path)
    print(f"zip: {zip_path} ({zip_path.stat().st_size / 1024 / 1024:.0f} MB)")
    if not args.so_empacotar:
        publicar(zip_path, args.regiao, args.min_tasks, args.max_tasks, s3, bucket, conta)
        garantir_versao_no_ar(args.regiao, conta)


if __name__ == "__main__":
    main()
