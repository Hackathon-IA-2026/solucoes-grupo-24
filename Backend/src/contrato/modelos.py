"""Modelos Pydantic do contrato, um para cada schema Zod de types.ts (mesma ordem, mesmas regras).

Convenções herdadas de types.ts:
- JSON em camelCase (aqui os atributos são snake_case e o alias camelCase é gerado);
- `mock` obrigatório em todo registro de nível superior;
- timestamps ISO-8601 em UTC com sufixo Z; potências em MW; percentuais 0–100 (sufixo Pct);
  frações 0–1.
- extra="forbid": campo que o dashboard não conhece é erro aqui, e não uma surpresa lá.

As validações de negócio do Zod (supervisionada = global − MMGD, quantis em ordem, motivos
somando 100%) estão repetidas aqui de propósito: o Backend recusa gravar no banco o que o
dashboard recusaria exibir. Um snapshot incoerente falha na publicação, não na tela.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated, Literal, NamedTuple

from pydantic import (AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer,
                      model_validator)
from pydantic.alias_generators import to_camel


def _utc(v: datetime) -> datetime:
    """Exige fuso e converte para UTC. Horário sem fuso seria ambíguo (UTC? UTC−3?)."""
    if v.tzinfo is None:
        raise ValueError("timestamp sem fuso: use UTC (sufixo Z) ou offset explícito")
    return v.astimezone(timezone.utc)


# Sempre sai como "2026-09-25T17:30:00Z" (formato que o z.iso.datetime({offset:false}) aceita).
TimestampUtc = Annotated[datetime, AfterValidator(_utc),
                         PlainSerializer(lambda v: v.strftime("%Y-%m-%dT%H:%M:%SZ"), return_type=str)]
Mw = Annotated[float, Field(allow_inf_nan=False)]
Pct = Annotated[float, Field(ge=0, le=100)]

Horizonte = Literal["30min", "3h", "D+1"]
Severidade = Literal["low", "medium", "high", "critical"]
Razao = Literal["REL", "CNF", "ENE"]
FonteGeracao = Literal["Eólica", "Solar FV"]
HorizonteExcedente = Literal["1h", "3h", "D+1"]

# Posição geográfica (WGS84), limitada a uma caixa em torno do Brasil (mesmos limites de
# `posicao` no types.ts): lat/lon trocados ou com sinal errado caem fora e são recusados na
# PUBLICAÇÃO, em vez de virar um ponto no oceano no Mapa Híbrido.
Latitude = Annotated[float, Field(ge=-34, le=6)]
Longitude = Annotated[float, Field(ge=-74, le=-28)]


class Modelo(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    def para_json(self) -> dict:
        """Dict pronto para o dashboard (aliases camelCase, timestamps com Z)."""
        return self.model_dump(mode="json", by_alias=True)


class Registro(Modelo):
    mock: bool


# --------------------------------------------------------------------------- 1. CargaSnapshot
class CargaSnapshot(Registro):
    timestamp_utc: TimestampUtc
    carga_global_mw: Mw
    mmgd_estimada_mw: Mw
    carga_supervisionada_mw: Mw
    percentual_mmgd_na_geracao: Pct
    mmgd_sobre_capacidade_instalada: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _supervisionada(self):
        # Regra do projeto: carga supervisionada = carga global − MMGD estimada (tolerância 1 MW).
        if abs(self.carga_global_mw - self.mmgd_estimada_mw - self.carga_supervisionada_mw) > 1:
            raise ValueError("cargaSupervisionadaMw deve ser cargaGlobalMw − mmgdEstimadaMw (tolerância 1 MW)")
        return self


# --------------------------------------------------------------------------- 2. PrevisaoCurva
class PontoPrevisao(Modelo):
    timestamp: TimestampUtc
    p10: Mw
    p50: Mw
    p90: Mw

    @model_validator(mode="after")
    def _quantis(self):
        if not (self.p10 <= self.p50 <= self.p90):
            raise ValueError("quantis fora de ordem (p10 ≤ p50 ≤ p90)")
        return self


class FatoresClimaticos(Modelo):
    radiacao_solar: float = Field(ge=0)  # W/m²
    vento_ms: float = Field(ge=0)
    temperatura_c: float
    cobertura_nuvens_pct: Pct


class PrevisaoCurva(Registro):
    horizonte: Horizonte
    pontos: list[PontoPrevisao] = Field(min_length=1)
    rampa_projetada_mw: Mw
    janela_rampa_horas: float = Field(gt=0)
    fatores_climaticos: FatoresClimaticos


# --------------------------------------------------------------------------- 3. RiscoUsina
class RiscoUsina(Registro):
    id: str = Field(min_length=1)
    nome: str = Field(min_length=1)
    uf: str = Field(min_length=2, max_length=2)
    # posição da usina/subestação no Mapa Híbrido
    lat: Latitude
    lon: Longitude
    distribuidora: str = Field(min_length=1)
    fonte: FonteGeracao
    razao: Razao
    probabilidade_pct: Pct
    montante_mw: Mw
    horizonte: Horizonte
    severidade: Severidade
    acao_recomendada: str = Field(min_length=1)


# --------------------------------------------------------------------------- 4. AlertaDetalhado
class ShapValue(Modelo):
    variavel: str = Field(min_length=1)
    peso: float = Field(ge=0, le=1)
    direcao: Literal["aumenta", "reduz"]


class Motivo(Modelo):
    razao: Razao
    peso_pct: Pct


class AlertaDetalhado(Registro):
    risco_usina_id: str = Field(min_length=1)
    probabilidade_pct: Pct
    montante_mw: Mw
    horario_previsto: TimestampUtc
    motivos: list[Motivo] = Field(min_length=1)
    fonte_dataset: str = Field(min_length=1)
    janela_previsao: Horizonte
    atualizado_ha_min: int = Field(ge=0)
    atualizado_em: TimestampUtc
    metodo_explicacao: str = Field(min_length=1)
    shap_values: list[ShapValue]
    texto_alerta: str = Field(min_length=1)

    @model_validator(mode="after")
    def _motivos_somam_100(self):
        if abs(sum(m.peso_pct for m in self.motivos) - 100) > 0.5:
            raise ValueError("a soma de motivos[].pesoPct deve ser 100")
        return self


# --------------------------------------------------------------------------- 5. ExcedenteTsoDso
class ExcedenteTsoDso(Registro):
    area_concessao: str = Field(min_length=1)
    distribuidora: str = Field(min_length=1)
    # ponto representativo da área (fronteira TSO-DSO) no Mapa Híbrido
    lat: Latitude
    lon: Longitude
    fonte: str = Field(min_length=1)
    excedente_mw: Mw
    prioridade: Severidade
    horizonte: HorizonteExcedente
    acao_recomendada: str = Field(min_length=1)


# --------------------------------------------------------------------------- 6. MetricasValidacao
class ErroDiario(Modelo):
    data: date
    mae: Mw
    rmse: Mw
    mae_baseline: Mw
    rmse_baseline: Mw


class Periodo(Modelo):
    inicio: date
    fim: date


class ModeloInfo(Modelo):
    """Metadados do modelo avaliado na tela Validação."""
    nome: str = Field(min_length=1)
    versao: str = Field(min_length=1)
    data_treino: date
    # períodos do split CRONOLÓGICO (regra do projeto: nunca aleatório)
    periodo_treino: Periodo
    periodo_teste: Periodo

    @model_validator(mode="after")
    def _split_cronologico(self):
        # Mesmo refine do types.ts: teste começa depois do fim do treino (sem vazamento temporal).
        if not self.periodo_treino.fim < self.periodo_teste.inicio:
            raise ValueError("periodoTeste deve começar depois do fim do periodoTreino (split cronológico)")
        return self


class StatusFonte(Modelo):
    fonte: str = Field(min_length=1)
    online: bool
    ultima_sincronizacao: TimestampUtc


class MetricasValidacao(Registro):
    erro_medio_absoluto_mw: Mw
    rmse_mw: Mw
    mape_pct: float = Field(ge=0)
    skill_vs_climatologia: float = Field(le=1)
    # nome do baseline comparado no histórico (ex.: "Climatologia")
    baseline_nome: str = Field(min_length=1)
    # Alias explícito: o gerador automático produziria "historicoErro30D" (maiúscula depois do
    # dígito); o nome no types.ts é "historicoErro30d". O teste dos mocks pegou isso.
    historico_erro30d: list[ErroDiario] = Field(alias="historicoErro30d")
    modelo: ModeloInfo
    status_fontes: list[StatusFonte]


# --------------------------------------------------------------------------- 7. DensidadeMmgd
# [lat, lon, intensidade 0–1]: formato direto do leaflet.heat (tupla, não objeto).
PontoCalor = tuple[Latitude, Longitude, Annotated[float, Field(ge=0, le=1)]]


class DensidadeMmgd(Registro):
    """Camada de calor do Mapa Híbrido."""
    descricao: str = Field(min_length=1)
    pontos: list[PontoCalor] = Field(min_length=1)


# --------------------------------------------------------------------------- 8. AreasInfluencia
# GeoJSON (RFC 7946) das áreas de influência das subestações da área piloto: camada de polígonos
# do Mapa Híbrido. É um FeatureCollection comum (o Leaflet desenha direto), com o `mock` do
# contrato como membro extra do objeto (permitido pela RFC 7946 §6.1).
def _dentro_do_brasil(coords) -> None:
    """Percorre as coordenadas [lon, lat] (qualquer aninhamento) e exige a caixa do Brasil."""
    if coords and isinstance(coords[0], (int, float)):
        lon, lat = coords[0], coords[1]
        if not (-74 <= lon <= -28 and -34 <= lat <= 6):
            raise ValueError(f"coordenada fora do Brasil (lon, lat) = ({lon}, {lat}): ordem trocada?")
        return
    for c in coords:
        _dentro_do_brasil(c)


class GeometriaArea(Modelo):
    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list

    @model_validator(mode="after")
    def _coordenadas(self):
        # GeoJSON é [lon, lat] (ao contrário de lat/lon do resto do contrato): trocar a ordem
        # jogaria o RJ no oceano Índico; aqui isso falha na publicação.
        _dentro_do_brasil(self.coordinates)
        # Mesma regra do GeometriaAreaSchema (types.ts): polígono com pelo menos um anel e anel
        # fechado com pelo menos 4 pontos. Sem isto, um polígono vazio (semente de 10 m que a
        # simplificação para a web apagou) passou pelo Backend e derrubou o Mapa Híbrido.
        poligonos = [self.coordinates] if self.type == "Polygon" else self.coordinates
        if not poligonos or any(not aneis or any(len(a) < 4 for a in aneis) for aneis in poligonos):
            raise ValueError(f"{self.type} vazio ou com anel de menos de 4 pontos")
        return self


class PropriedadesArea(Modelo):
    area_id: str = Field(min_length=1)          # "<distribuidora>:<código da subestação>"
    nome: str = Field(min_length=1)             # nome da subestação
    distribuidora: str = Field(min_length=1)
    classificacao: str = Field(min_length=1)    # plena, satélite, transformadora pura, transporte
    area_mae: str | None                        # subestação que alimenta esta (satélites)
    lat_sub: Latitude                           # posição da subestação
    lon_sub: Longitude
    area_km2: float = Field(ge=0)
    capacidade_mmgd_mw: Mw = Field(ge=0)        # cadastrada (ANEEL), localizada pela BDGD
    capacidade_lag_mw: Mw = Field(ge=0)         # parte que ainda não está na BDGD (lag de sistema)
    fator_correcao: float | None = Field(default=None, gt=0)  # satélite (Luiz); null = sem correção
    # Excedente previsto nas próximas 24 h, só para subestação de FRONTEIRA (origem de
    # alimentadores); null nas que não conectam alimentadores próprios (ex.: satélites).
    excedente_mw: Mw | None = Field(default=None, ge=0)
    horizonte_excedente: HorizonteExcedente | None = None


class FeatureArea(Modelo):
    type: Literal["Feature"]
    geometry: GeometriaArea
    properties: PropriedadesArea


class AreasInfluencia(Registro):
    """Camada de polígonos do Mapa Híbrido: uma área de influência por subestação."""
    type: Literal["FeatureCollection"]
    descricao: str = Field(min_length=1)
    features: list[FeatureArea] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids_unicos(self):
        ids = [f.properties.area_id for f in self.features]
        if len(ids) != len(set(ids)):
            raise ValueError("areaId repetido nas áreas de influência")
        return self


# --------------------------------------------------------------------------- recursos
class DefRecurso(NamedTuple):
    modelo: type[Registro]
    lista: bool          # o recurso é uma coleção (no banco: um item por linha)
    rota: str            # caminho na API, sem o prefixo (config/api.yaml)


# Cada recurso da API: modelo do item, lista ou objeto, e a rota. É a tabela que liga
# contrato, banco, API (src/api/app.py gera as rotas daqui) e o schema documentado
# (src/contrato/esquema.py): acrescentar recurso = uma linha aqui + o mesmo no types.ts.
# A rota tem de ser a mesma de ENDPOINTS em Frontend/.../src/data/dataSource.ts.
RECURSOS: dict[str, DefRecurso] = {
    "carga": DefRecurso(CargaSnapshot, False, "/carga/snapshot"),
    "previsao": DefRecurso(PrevisaoCurva, True, "/previsao"),
    "riscos": DefRecurso(RiscoUsina, True, "/riscos"),
    # coleção no banco, mas a rota devolve UM alerta por id (404 se não houver)
    "alertas": DefRecurso(AlertaDetalhado, True, "/alertas/{id}"),
    "excedentes": DefRecurso(ExcedenteTsoDso, True, "/excedentes"),
    "validacao": DefRecurso(MetricasValidacao, False, "/validacao"),
    "mmgd_densidade": DefRecurso(DensidadeMmgd, False, "/mmgd/densidade"),
    "areas_influencia": DefRecurso(AreasInfluencia, False, "/areas-influencia"),
}
