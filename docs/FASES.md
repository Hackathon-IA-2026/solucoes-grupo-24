# Fases do backend — acompanhamento

Checklist de execução do plano (`docs/Oraculo_planejamento.md`, seções 10 e 13). **Atualizar a cada tarefa concluída**: marcar `[x]`, e o detalhe do que foi feito vai para `docs/STATUS.md`.

Legenda: `[x]` feito · `[ ]` a fazer · **(nunca cortar)** / *(cortável)* conforme o `CLAUDE.md` · 🔒 bloqueado (motivo ao lado) · 👤 depende de decisão ou ação humana.

Ordem: cada fase libera telas do dashboard (coluna "Libera"). A ordem segue o que o frontend precisa, não a numeração das fatias do PDF.

| Fase | Nome | Fatia do plano | Libera no dashboard | Situação |
|---|---|---|---|---|
| 0 | Fundação do repositório | — | — | ✅ |
| 1 | Dados: ingestão e processamento | 1 | — | 🟡 falta qualidade, histórico e episódios |
| 2 | Banco, API e publicação | 6 (parte) | Visão Geral (real) | ✅ dashboard ligado na API |
| 3 | Baseline de carga | 2 | Despacho Preditivo, Validação | ✅ falta só fonte meteorológica (fatores climáticos) |
| 4 | Classificador de curtailment ENE | 5 | Lista de Riscos, Detalhe do Alerta | 🟡 código e testes prontos; falta a 1ª execução com dado real, `distribuidora` (Luiz) e lead time |
| 5 | TFT com perda assimétrica | 3 | Despacho Preditivo (melhor modelo) | ⬜ 🔒 torch |
| 6 | Espacialização: MMGD por área de influência da subestação e excedentes | 4 e 5 | Excedentes, Mapa Híbrido | 🟡 RJ pronto; falta fator do satélite (Luiz) e contrato das áreas de influência |
| 7 | Entrega: pitch, prova documental, README | 1 e 6 | — | ⬜ |

---

## Fase 0 — Fundação do repositório ✅

- [x] Estrutura `Backend/`, `Frontend/`, `docs/` (garantida por teste)
- [x] `pyproject.toml`, `.venv`, `.gitignore` (dados brutos fora do git)
- [x] Config centralizada em `Backend/config/*.yaml`
- [x] README no modelo da competição
- [x] Notebooks Jupyter removidos (análise é código do backend; teste impede a volta)
- [x] Plano transcrito em `docs/Oraculo_planejamento.md`, com adendo de decisões (§13)

## Fase 1 — Dados: ingestão e processamento 🟡

Ingestão
- [x] Inventário do portal ONS e do MCP oficial
- [x] Catálogo de séries **(nunca cortar)**
- [x] Download idempotente: 15 conjuntos do ONS, API de carga e cadastro de MMGD da ANEEL
- [x] Detecção de arquivo republicado no portal; cadastro da ANEEL expira em 7 dias
- [x] Consolidação das bases detail sem duplicar meses rebaixados

Processamento
- [x] Mapeamento subsistema × área de carga (único caminho de cruzamento)
- [x] Calendário (feriados = domingo, patamares, faixas de curtailment, Dia dos Pais)
- [x] Carga supervisionada = carga global − MMGD, 30 min, por subsistema
- [x] Rótulos de curtailment por razão (ENE, CNF, REL), chave fonte + id
- [x] Capacidade de MMGD por UF e data (ANEEL, sem colunas pessoais)
- [ ] **Peça A — qualidade das bases**: checagem contra o dicionário do ONS, nulos, duplicatas, buracos → `docs/reports/`; alimenta o status das fontes na tela Validação
- [ ] *Peça B — histórico mensal de curtailment por razão × capacidade × carga* (Figura 1 do pitch: "ENE domina desde abr/2025?")
- [ ] *Peça C — episódios de corte e o caso real de restrição total* (prova documental; também serve ao backtest da Fase 4)

Orquestração
- [x] `run_heavywork.py`: script único, sem argumentos, pula etapas em dia
- [x] Teste: só ingestão e processamento tocam `data/raw`

## Fase 2 — Banco, API e publicação ✅

- [x] Contrato oficial = `types.ts` do dashboard; espelho Pydantic; `docs/schema_contrato.json` gerado **(JSON do contrato: nunca cortar)**
- [x] Banco: SQLAlchemy 2 + Alembic, factory única (`DATABASE_URL` ou SQLite)
- [x] Publicação (etapa 5): função única que monta o contrato → `output/contrato.json` + banco
- [x] Visão Geral com **carga real**; demais recursos mock com `mock: true`
- [x] API FastAPI (`main.py`): 6 rotas do contrato + `/api/saude`, só leitura
- [x] Testes: contrato × mocks do dashboard, migrations × modelos, API sem a parte pesada
- [x] Contrato v3 (telas Excedentes, Validação e Mapa Híbrido): `lat`/`lon`, baseline e metadados do modelo na validação, recurso `mmgd_densidade`; rotas da API geradas de `RECURSOS` (2026-09-26)
- [x] Dashboard ligado na API: modo `api` padrão, proxy `/api` lido de `config/api.yaml`, `main.py` serve o build, pill de origem dos dados (2026-09-26)
- [ ] 👤 **Luiz**: definir o que o campo `distribuidora` mostra na lista de riscos

## Fase 3 — Baseline de carga (Fatia 2) ✅

Base comum
- [x] Módulo de features compartilhadas: `src/features/defasagens.py` (defasagens que recusam olhar depois da emissão), `src/features/carga.py`, calendário
- [x] Split cronológico único (`src/models/split.py`, datas em `config/modelos_carga.yaml`) + **testes de vazamento temporal** (features com futuro perturbado; treino idêntico mudando o teste inteiro)
- [x] Meteorologia (ERA5): decidido 2026-09-25 — por enquanto só calendário + defasagens

Modelos **(nunca cortar)**
- [x] Persistência
- [x] Sazonal-naïve (mesmo horário do dia anterior e da semana anterior) + climatologia (base do skill)
- [x] Gradient boosting (LightGBM) com quantis P10/P50/P90, banda calibrada por conformal (CQR)
- [x] Horizontes 30 min, 3 h e D+1 (h = 1, 6, 48), por subsistema e SIN

Avaliação
- [x] Backtest cronológico (teste: jul/2025 → set/2026, fora da amostra)
- [x] Métricas por patamar (mínima diurna, rampa vespertina, ponta noturna): MAE, RMSE, MAPE, pinball, cobertura, erro de pico, vale e rampa
- [x] Relatório em `docs/reports/baseline_carga.md` (+ `metricas_carga.csv`): LightGBM ganha do melhor baseline nas 15 combinações série × horizonte

Integração
- [x] Etapas `treino_carga` e `previsao_carga` do `run_heavywork.py`
- [x] Previsão (modo replay): todas as emissões desde o início do teste; a publicação escolhe o "agora"
- [x] Publicar `previsao` com pontos reais (P10/P50/P90 + rampa); registro `mock: true` só por causa dos fatores climáticos
- [x] Publicar `validacao` real (métricas do backtest do SIN no D+1 + status das fontes vindo do manifesto de download)
- [ ] 🔒👤 `fatoresClimaticos` da previsão: só com fonte meteorológica, ou o contrato aceitar o campo vazio (combinar com o Luiz)

## Fase 4 — Classificador de curtailment ENE (Fatia 5) 🟡 falta rodar com dado real (métricas ainda não medidas)

- [x] Features (`src/features/curtailment.py`): histórico de cortes da usina, estado do sistema (fração de usinas cortando no subsistema e no SIN), carga supervisionada e MMGD, faixas horárias, calendário, atributos da usina
- [x] Split cronológico (treino abr/2023 → dez/2025, teste 2026) + testes de vazamento e de códigos de usina estáveis
- [x] **Classificador ENE** (probabilidade de corte por usina/conjunto, 3 horizontes) **(nunca cortar)**
- [x] Montante esperado = P(corte) × E[MW | corte]
- [x] Métricas: ROC-AUC, PR-AUC, Brier, precisão/recall, erro de montante, contra persistência e frequência recente (`docs/reports/classificador_curtailment.md`)
- [ ] Lead time útil (antecedência com que o risco sobe antes do início de um episódio de corte) — depende da Peça C (episódios)
- [x] Explicabilidade com SHAP exato do LightGBM (`ExplicadorLightGBM`), agrupado em rótulos legíveis
- [x] Publicar `alertas` reais; `riscos` reais exceto `distribuidora`
- [ ] 👤 **Luiz**: o que o campo `distribuidora` mostra (usinas da rede básica não têm distribuidora); até lá o risco sai `mock: true`
- [x] *Classificador CNF (cortável)*: roda com as mesmas features; 🔒 sem os limites de exportação NE e N/NE (não existem no portal nem no MCP)

## Fase 5 — TFT com perda assimétrica (Fatia 3) ⬜ 🔒

- [ ] 👤 Corrigir o torch no Windows (erro de DLL em `c10.dll`: Visual C++ Redistributable ou outra versão)
- [ ] Perda assimétrica por patamar, com pesos em `config/*.yaml` **(nunca cortar)**
- [ ] TFT com quantis P10/P50/P90 **(nunca cortar)**
- [ ] Comparação contra os baselines da Fase 3, por horizonte e patamar
- [ ] Publicar a previsão do melhor modelo (a tela não muda)

## Fase 6 — Espacialização: MMGD por área de influência da subestação e excedentes (Fatias 4 e 5) 🟡

Método completo em `docs/metodo_espacial.md`.

- [x] 👤 **Área piloto: RJ (LIGHT + Enel RJ)**, reaproveitando o RDX (Tiago, 2026-09-26) — 👤 avisar o Luiz (imagens de satélite)
- [x] Ingestão da BDGD da área piloto (etapa 1): BDGD 2025 LIGHT e Enel RJ + malhas do IBGE como arquivos diretos
- [x] Migrar a pipeline de `Backend/RDX/` para `src/spatial/` (áreas de influência, classificação e hierarquia, MMGD da BDGD)
- [x] Áreas de influência das subestações (um polígono por subestação) → `output/areas_influencia_rj.geojson`
- [x] Capacidade de MMGD por área de influência + desempate com o cadastro diário da ANEEL (Lag de Sistema × não homologada)
- [x] Pipeline da auditoria em 3 camadas pronto e testado em modo mock (Luiz, 2026-09-26): `pipeline/auditoria_camada1.py` (YOLO → GeoJSON), `auditoria_camadas_2_3.py` (desempate + fator por área de influência, não homologadas fora do fator), `validar_modelo.py`, `download_satelite.py`; parâmetros em `config/visao.yaml`
- [ ] 👤 Fator de correção por imagem de satélite (Luiz) — o gancho já existe (`caminho_fator_correcao`); falta rodar com imagem **submétrica** da área piloto (Sentinel-2, 10 m, não enxerga painel residencial)
- [ ] 👤 Gabarito para o YOLO (`gabarito.csv` com imagens da área): o modelo em uso (`best.pt`, versão antiga do treinamento do time, checkpoint de 2023) marcou "solar-panel" em fotos sem painel
- [x] Excedentes por subestação de fronteira (MMGD − carga, persistência sazonal), conferidos contra o fluxo reverso medido na BDGD
- [x] Publicar `excedentes` e `mmgd_densidade` reais (`mock: false`, schema inalterado)
- [ ] 👤 Contrato do Mapa Híbrido (áreas de influência em GeoJSON): combinar com o Luiz antes de mudar o schema
- [ ] Melhorar o excedente: fator de geração por área de influência (irradiância) e perfil de carga intradiário por classe

## Fase 7 — Entrega ⬜

- [ ] Figura 1 (vinda da Peça B da Fase 1)
- [ ] Caso real de constrained-off com o diagnóstico que o sistema teria dado (Peça C + Fase 4) — cenário `dia_dos_pais_2024` pronto em `python -m pipeline.teste_e2e` (extrai do dado real a carga mínima e a fração de usinas cortadas); falta rodar na máquina com as bases. Atenção: 2024-08-11 está no treino do classificador (in-sample)
- [x] Harness ponta a ponta `pipeline/teste_e2e.py` (status real/mock lido dos dados, relatório em `docs/reports/teste_e2e.md`) (2026-09-26)
- [x] Dashboard: revisão de design com o protótipo Figma, tela Metodologia, filtros de severidade ligados às telas, mapa sem tiles externos (2026-09-26)
- [ ] Definir a janela da demo (o "agora" do replay) em `config/publicacao.yaml`
- [ ] README: link da demo e dashboard (👤 Luiz)
- [ ] *Tool de previsão publicada no MCP do ONS (cortável)*

---

## Decisões pendentes (resumo)

| Decisão | Fase | Quem |
|---|---|---|
| Área piloto | 6 | ✅ Tiago (2026-09-26: RJ) → avisar Luiz |
| Meteorologia (ERA5) agora ou depois | 3 | ✅ Tiago (2026-09-25: depois) |
| `fatoresClimaticos` sem fonte meteorológica: manter mock ou aceitar vazio no contrato | 3 | Tiago + Luiz |
| Campo `distribuidora` do risco | 4 | Luiz |
| Correção do torch no Windows | 5 | Tiago |
| Janela da demo (replay) | 7 | Tiago |
