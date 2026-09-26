
"""
Este script cria uma interface web usando Streamlit e Folium para exibir um mapa interativo.
Ele utiliza um único arquivo GeoJSON unificado contendo tanto a geografia quanto as estatísticas.
Otimizado com PNGs rasterizados e renderização em massa para performance profissional.
"""
import streamlit as st
import folium
from streamlit_folium import st_folium
import geopandas as gpd
import geobr
from folium.plugins import Fullscreen, MousePosition, MeasureControl, AntPath
from folium.features import DivIcon
import os
import random
import base64
import re
import pandas as pd
import json
import urllib.parse
import plotly.express as px
import math
from scipy.spatial import KDTree
import numpy as np

# --- CONFIGURAÇÕES ---
ARQUIVO_UNIFICADO = os.path.join("Dados Processados", "dados_finais_rj.geojson")
ARQUIVO_PERFIS = os.path.join("Dados Processados", "perfis_consumo.csv")

# Cores por Distribuidora (para os marcadores)
CORES_DISTRIBUIDORA = {
    'LIGHT': 'red',
    'ENEL': 'blue'
}

# Configuração da página do Streamlit
st.set_page_config(page_title="Mapa LIGHT & ENEL RJ - Big Data", layout="wide")

@st.cache_data
def load_data():
    """
    Carrega o contorno do RJ, os dados unificados e os perfis de consumo.
    """
    print("DEBUG: Carregando contorno do Estado do Rio de Janeiro...")
    rj_shape = geobr.read_state(code_state="RJ", year=2020)
    rj_shape = rj_shape.to_crs("EPSG:4326")
    
    print(f"DEBUG: Carregando dados unificados de {ARQUIVO_UNIFICADO}...")
    gdf_unificado = None
    if os.path.exists(ARQUIVO_UNIFICADO):
        gdf_unificado = gpd.read_file(ARQUIVO_UNIFICADO)
    
    print(f"DEBUG: Carregando perfis de consumo de {ARQUIVO_PERFIS}...")
    df_perfis = None
    if os.path.exists(ARQUIVO_PERFIS):
        df_perfis = pd.read_csv(ARQUIVO_PERFIS, sep=';')
        
    # Preparar estruturas para lookup rápido
    if gdf_unificado is not None:
        # Dicionário de nomes para COD_ID
        subestacoes_dict = {row['NOM']: str(row['COD_ID']) for _, row in gdf_unificado.iterrows() if pd.notna(row['NOM'])}
        
        # Dicionário reverso para nomes
        id_to_nome = {str(row['COD_ID']): row['NOM'] for _, row in gdf_unificado.iterrows()}
        
        # KDTree para busca espacial por coordenadas
        points = np.array([[row['lat_sub'], row['lon_sub']] for _, row in gdf_unificado.iterrows()])
        ids = [str(row['COD_ID']) for _, row in gdf_unificado.iterrows()]
        tree = KDTree(points)
    else:
        subestacoes_dict = {}
        id_to_nome = {}
        tree = None
        ids = []
    
    return rj_shape, gdf_unificado, df_perfis, subestacoes_dict, id_to_nome, tree, ids

def gerar_html_popup(row, df_perfis=None):
    """
    Gera o conteúdo HTML para o popup a partir das propriedades do GeoJSON.
    """
    cod_id = str(row['COD_ID'])
    pot_nom = row.get('POT_NOM', 0)
    dist = row.get('DISTRIBUIDORA', 'N/A')
    classificacao = row.get('CLASSIFICACAO', 'Não Classificada')
    mae = row.get('SUB_MAE', 'N/A')
    
    stats_html = f'<div style="font-family: sans-serif; min-width: 280px; max-width: 350px;">'
    stats_html += f'<h4 style="margin: 0 0 10px 0; color: #333; border-bottom: 1px solid #ccc; padding-bottom: 5px;">{row["NOM"] or cod_id}</h4>'
    stats_html += f"<b>Distribuidora:</b> {dist}<br>"
    stats_html += f"<b>Classificação:</b> {classificacao}<br>"
    if mae and mae != '0' and mae != 'None':
        stats_html += f"<b>Alimentada por (ID):</b> {mae}<br>"
    stats_html += f"<b>Potência:</b> {row['POTENCIA_CALCULADA']:.2f} MVA<br>"
    if pot_nom and pot_nom > 0:
        stats_html += f"<b>Potência Nominal:</b> {pot_nom:.2f} MVA<br>"
    
    stats_html += "<div style='margin-top: 10px;'>"
    
    # --- ADICIONAR PERFIS DE CONSUMO (NOVO) ---
    if df_perfis is not None:
        sub_perfis = df_perfis[df_perfis['COD_ID'].astype(str) == cod_id]
        if not sub_perfis.empty:
            stats_html += "<hr style='margin: 10px 0; border-top: 2px solid #333;'>"
            stats_html += "<b>📊 Perfil de Consumo (BDGD):</b><br>"
            
            # Tabela de Classes
            stats_html += "<table style='width:100%; font-size: 11px; border-collapse: collapse; margin-top: 5px;'>"
            stats_html += "<tr style='background: #eee;'><th>Classe</th><th>Qtd</th><th>Carga Instalada (kW)</th></tr>"
            
            total_carga_instalada = 0
            consumo_mensal = [0.0] * 12
            
            for _, p_row in sub_perfis.iterrows():
                classe_nome = p_row['CLASSE'].replace('_', ' ').title()
                carga_inst = float(p_row['SOMA_CAR_INST'])
                stats_html += f"<tr><td>{classe_nome}</td><td align='right'>{int(p_row['QTD_CLIENTES'])}</td><td align='right'>{carga_inst:.1f}</td></tr>"
                
                total_carga_instalada += carga_inst
                
                # Somar energia para sazonalidade
                for i in range(1, 13):
                    val = float(p_row.get(f'ENE_{i:02d}', 0))
                    consumo_mensal[i-1] += val
            
            stats_html += "</table>"
            stats_html += f"<div style='margin-top: 5px; font-weight: bold; color: #d32f2f;'>Carga Instalada Total: {total_carga_instalada:.1f} kW</div>"
            
            # --- GRÁFICO DE PIZZA (SVG NATIVO - ULTRA ROBUSTO) ---
            if total_carga_instalada > 0:
                print(f"DEBUG: Gerando gráfico SVG para COD_ID {cod_id}...")
                
                # Preparar dados e agrupar "Outros" (< 5%)
                data_map = {}
                for _, p_row in sub_perfis.iterrows():
                    classe = p_row['CLASSE'].replace('_', ' ').title()
                    carga = float(p_row['SOMA_CAR_INST'])
                    data_map[classe] = data_map.get(classe, 0) + carga
                
                limiar = 0.05 * total_carga_instalada
                final_data = {"Outros": 0}
                for classe, carga in data_map.items():
                    if carga < limiar:
                        final_data["Outros"] += carga
                    else:
                        final_data[classe] = carga
                
                if final_data["Outros"] == 0:
                    del final_data["Outros"]
                
                labels = list(final_data.keys())
                values = [v for v in final_data.values()]
                colors = ['#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4', '#46f0f0', '#f032e6', '#bcf60c']
                
                # Gerar SVG
                svg_html = f'<svg width="140" height="140" viewBox="-1 -1 2 2" style="transform: rotate(-90deg); display: block; margin: 10px auto; filter: drop-shadow(0 2px 3px rgba(0,0,0,0.2));">'
                svg_html += '<style>path { transition: opacity 0.2s; cursor: pointer; } path:hover { opacity: 0.7; }</style>'
                cumulative_percent = 0
                for i, (label, val) in enumerate(zip(labels, values)):
                    percent = val / total_carga_instalada
                    color = colors[i % len(colors)]
                    
                    start_x = math.cos(2 * math.pi * cumulative_percent)
                    start_y = math.sin(2 * math.pi * cumulative_percent)
                    cumulative_percent += percent
                    end_x = math.cos(2 * math.pi * cumulative_percent)
                    end_y = math.sin(2 * math.pi * cumulative_percent)
                    
                    large_arc = 1 if percent > 0.5 else 0
                    path_data = f"M {start_x} {start_y} A 1 1 0 {large_arc} 1 {end_x} {end_y} L 0 0"
                    
                    svg_html += f'<path d="{path_data}" fill="{color}" stroke="white" stroke-width="0.01">'
                    svg_html += f'<title>{label}: {val:.1f} kW ({percent:.1%})</title>'
                    svg_html += f'</path>'
                
                svg_html += '<circle cx="0" cy="0" r="0.4" fill="white" /></svg>' # Donut hole
                
                # Adicionar Legenda Customizada em HTML
                stats_html += f'<div style="margin-top: 15px; padding: 10px; border: 1px solid #eee; border-radius: 8px; background: #fdfdfd; text-align: center;">'
                stats_html += f'<div style="font-size: 12px; font-weight: bold; margin-bottom: 8px; color: #333;">Distribuição de Carga</div>'
                stats_html += svg_html
                
                stats_html += '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 5px; text-align: left; margin-top: 10px;">'
                for i, (label, val) in enumerate(zip(labels, values)):
                    color = colors[i % len(colors)]
                    pct = (val / total_carga_instalada) * 100
                    stats_html += f'<div style="font-size: 10px; display: flex; align-items: center;">'
                    stats_html += f'<span style="width: 8px; height: 8px; background: {color}; display: inline-block; margin-right: 5px; border-radius: 2px;"></span>'
                    stats_html += f'<span>{label}: <b>{pct:.1f}%</b></span>'
                    stats_html += f'</div>'
                stats_html += '</div></div>'
            # Tabela de Sazonalidade (12 meses)
            stats_html += "<div style='margin-top: 10px;'><b>📅 Sazonalidade (kWh):</b></div>"
            stats_html += "<div style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 2px; font-size: 9px; margin-top: 3px;'>"
            meses_abrev = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
            for i, m_nome in enumerate(meses_abrev):
                stats_html += f"<div style='background:#f0f0f0; padding: 2px; text-align:center;'>{m_nome}<br><b>{consumo_mensal[i]/1000:.1f}k</b></div>"
            stats_html += "</div>"
            
            media_mensal = sum(consumo_mensal) / 12
            stats_html += f"<div style='margin-top: 8px; font-size: 11px; font-weight: bold; color: #1565c0;'>Média(12 meses): {media_mensal/1000:.1f}k kWh</div>"
    # --- ADICIONAR DADOS DE MMGD (NOVO) ---
    total_mmgd = row.get('TOTAL_MMGD_KW', 0)
    if total_mmgd > 0:
        stats_html += "<hr style='margin: 10px 0; border-top: 2px solid #fbc02d;'>"
        stats_html += "<b>☀️ Geração Distribuída (MMGD):</b><br>"
        stats_html += f"<b>Potência Instalada:</b> {total_mmgd:.1f} kW<br>"
        stats_html += f"<b>Qtd. Usinas:</b> {int(row.get('QTD_USINAS', 0))}<br>"
        
        energia_anual_mmgd = row.get('ENERGIA_MMGD_ANUAL', 0)
        stats_html += f"<b>Energia Injetada (Ano):</b> {energia_anual_mmgd/1000:.1f}M kWh<br>"
        
        # Sazonalidade MMGD
        stats_html += "<div style='margin-top: 5px;'><b>📅 Injeção Mensal (kWh):</b></div>"
        stats_html += "<div style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 2px; font-size: 9px; margin-top: 3px;'>"
        meses_abrev = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
        for i, m_nome in enumerate(meses_abrev):
            val_mes = row.get(f'ENE_MMGD_{i+1:02d}', 0)
            stats_html += f"<div style='background:#fff9c4; padding: 2px; text-align:center;'>{m_nome}<br><b>{val_mes/1000:.1f}k</b></div>"
        stats_html += "</div>"
    stats_html += "</div></div>"
    return stats_html

def get_image_base64(icon_name):
    """
    Converte uma imagem (PNG/SVG) para string Base64.
    """
    path = os.path.join("assets", "icons", icon_name)
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
            ext = icon_name.split('.')[-1]
            return f"data:image/{ext};base64,{data}"
    return None

@st.cache_resource
def create_map_object(_rj_shape, _gdf_unificado, _df_perfis):
    """
    Cria o objeto de mapa Folium otimizado com ícones PNG e popups completos.
    """
    print("DEBUG: Iniciando criação do objeto de mapa otimizado...")
    
    m = folium.Map(
        location=[-22.5, -42.5], # Centralizado mais para o meio do estado
        zoom_start=8, # Zoom reduzido para ver o estado todo
        control_scale=True,
        prefer_canvas=True
    )
    
    # Tiles
    folium.TileLayer('openstreetmap', name='OpenStreetMap').add_to(m)
    folium.TileLayer('cartodbpositron', name='CartoDB Positron').add_to(m)
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google', name='Satélite (Google)', overlay=False
    ).add_to(m)
    
    # Contorno RJ
    folium.GeoJson(
        _rj_shape.simplify(0.001), name="Contorno Rio de Janeiro",
        style_function=lambda x: {'fillColor': 'none', 'color': 'yellow', 'weight': 2}
    ).add_to(m)
    
    if _gdf_unificado is not None:
        # Carregar ícones PNG em Base64 e definir proporções reais
        icons_config = {
            "raio": {"url": get_image_base64("raio.png"), "ratio": 73/128},
            "satelite": {"url": get_image_base64("satelite.png"), "ratio": 1.0},
            "transformador": {"url": get_image_base64("transformador.png"), "ratio": 1.0},
            "torre": {"url": get_image_base64("torre.png"), "ratio": 1.0}
        }
        # Mapeamento de Categorias
        categories = {
            "1. Distribuição Plena": ("⚡ SE: Distribuição Plena", icons_config["raio"]),
            "2. Distribuição Satélite": ("📡 SE: Distribuição Satélite", icons_config["satelite"]),
            "3. Transformadora Pura": ("🔄 SE: Transformadora Pura", icons_config["transformador"]),
            "4. Transporte/Manobra": ("🏗️ SE: Transporte/Manobra", icons_config["torre"])
        }
        hierarchy_group = folium.FeatureGroup(name="🔗 Hierarquia de Alimentação", show=False).add_to(m)
        coords_subs = {str(row['COD_ID']): (row['lat_sub'], row['lon_sub']) for _, row in _gdf_unificado.iterrows()}
        cores_vibrantes = [
            '#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4',
            '#46f0f0', '#f032e6', '#bcf60c', '#fabebe', '#008080', '#e6beff',
            '#9a6324', '#fffac8', '#800000', '#aaffc3', '#808000', '#ffd8b1'
        ]
        # --- RENDERIZAÇÃO ---
        for base_classif, (group_name, icon_config) in categories.items():
            group = folium.FeatureGroup(name=group_name).add_to(m)
            
            mask = _gdf_unificado['CLASSIFICACAO'].str.contains(base_classif, na=False)
            gdf_cat = _gdf_unificado[mask].copy()
            
            if gdf_cat.empty: continue
            # Gerar HTML do popup para cada linha e salvar no GeoDataFrame
            gdf_cat['popup_html'] = gdf_cat.apply(lambda row: gerar_html_popup(row, _df_perfis), axis=1)
            # Polígonos em massa (Simplificados)
            gdf_cat['geometry'] = gdf_cat['geometry'].simplify(0.0001)
            gdf_cat['color'] = [cores_vibrantes[i % len(cores_vibrantes)] for i in range(len(gdf_cat))]
            
            folium.GeoJson(
                gdf_cat,
                style_function=lambda x: {
                    'fillColor': x['properties']['color'], 'color': 'white', 'weight': 1, 'fillOpacity': 0.3
                },
                tooltip=folium.GeoJsonTooltip(fields=['NOM'], aliases=['Área:']),
                popup=folium.GeoJsonPopup(fields=['popup_html'], labels=False)
            ).add_to(group)
            # Marcadores PNG
            icon_url = icon_config["url"]
            ratio = icon_config["ratio"]
            for _, row in gdf_cat.iterrows():
                pot = row.get('POTENCIA_CALCULADA', 0)
                base_size = 25 + min(45, pot / 10.0)
                
                if icon_url:
                    if ratio <= 1: # Mais alto que largo
                        height = base_size
                        width = base_size * ratio
                    else: # Mais largo que alto
                        width = base_size
                        height = base_size / ratio
                    folium.Marker(
                        location=[row['lat_sub'], row['lon_sub']],
                        icon=folium.CustomIcon(icon_url, icon_size=(int(width), int(height))),
                        popup=folium.Popup(row['popup_html'], max_width=350),
                        tooltip=f"SE: {row['NOM']}"
                    ).add_to(group)
                else:
                    folium.CircleMarker(
                        location=[row['lat_sub'], row['lon_sub']],
                        radius=min(15, 4 + (pot / 50.0)),
                        color='white', weight=1, fill=True, fill_color='gray', fill_opacity=1,
                        popup=folium.Popup(row['popup_html'], max_width=350),
                        tooltip=f"SE: {row['NOM']}"
                    ).add_to(group)
        # 3. Fluxo de Alimentação (AntPath)
        for _, row in _gdf_unificado.iterrows():
            mae_id = str(row.get('SUB_MAE', ''))
            if mae_id and mae_id in coords_subs and mae_id != str(row['COD_ID']):
                mae_coords = coords_subs[mae_id]
                filha_coords = (row['lat_sub'], row['lon_sub'])
                AntPath(
                    locations=[mae_coords, filha_coords],
                    color='white', pulse_color='yellow', weight=3, opacity=0.9,
                    delay=800, dash_array=[10, 20],
                    tooltip=f"Fluxo: {mae_id} -> {row['NOM']}"
                ).add_to(hierarchy_group)
    # Controles
    Fullscreen().add_to(m)
    MousePosition().add_to(m)
    MeasureControl().add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    
    return m

def render_dashboard(gdf_unificado, df_perfis, selected_cod_id, id_to_nome):
    try:
        row = gdf_unificado[gdf_unificado['COD_ID'].astype(str) == selected_cod_id].iloc[0]
        nome_sub = id_to_nome.get(selected_cod_id, selected_cod_id)
        
        st.header(f"Dashboard: {nome_sub} (COD_ID: {selected_cod_id})")
        
        # Métricas básicas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Distribuidora", row.get('DISTRIBUIDORA', 'N/A'))
        with col2:
            st.metric("Classificação", row.get('CLASSIFICACAO', 'Não Classificada'))
        with col3:
            st.metric("Potência Calculada", f"{row['POTENCIA_CALCULADA']:.2f} MVA")
        
        # Carga Instalada
        st.subheader("📊 Perfil de Consumo (Carga Instalada)")
        sub_perfis = df_perfis[df_perfis['COD_ID'].astype(str) == selected_cod_id]
        if not sub_perfis.empty:
            total_carga = sub_perfis['SOMA_CAR_INST'].sum()
            df_classes = sub_perfis[['CLASSE', 'QTD_CLIENTES', 'SOMA_CAR_INST']].copy()
            df_classes['CLASSE'] = df_classes['CLASSE'].str.replace('_', ' ').str.title()
            df_classes.columns = ['Classe', 'Qtd Clientes', 'Carga Instalada (kW)']
            st.dataframe(df_classes.style.format({'Carga Instalada (kW)': '{:.1f}'}))
            st.metric("Carga Instalada Total", f"{total_carga:.1f} kW")
            
            # Gráfico de Pizza
            fig_pie = px.pie(df_classes, values='Carga Instalada (kW)', names='Classe', title='Distribuição de Carga')
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Dados de carga instalada não disponíveis para esta subestação.")
        
        # Sazonalidade
        st.subheader("📅 Sazonalidade de Consumo")
        if not sub_perfis.empty:
            consumo_mensal = [sub_perfis[f'ENE_{i:02d}'].sum() for i in range(1, 13)]
            if sum(consumo_mensal) > 0:
                meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
                df_sazon = pd.DataFrame({'Mês': meses, 'Consumo (kWh)': consumo_mensal})
                fig_bar = px.bar(df_sazon, x='Mês', y='Consumo (kWh)', title='Sazonalidade Mensal')
                st.plotly_chart(fig_bar, use_container_width=True)
                media = sum(consumo_mensal) / 12
                st.metric("Média Mensal (12 meses)", f"{media / 1000:.1f}k kWh")
            else:
                st.info("Dados de sazonalidade não disponíveis ou zerados.")
        else:
            st.info("Dados de sazonalidade não disponíveis para esta subestação.")
        
        # MMGD
        st.subheader("☀️ Geração Distribuída (MMGD)")
        total_mmgd = row.get('TOTAL_MMGD_KW', 0)
        if total_mmgd > 0:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Potência Instalada", f"{total_mmgd:.1f} kW")
            with col2:
                st.metric("Qtd. Usinas", int(row.get('QTD_USINAS', 0)))
            with col3:
                energia_anual = row.get('ENERGIA_MMGD_ANUAL', 0)
                st.metric("Energia Injetada (Ano)", f"{energia_anual / 1000:.1f}M kWh")
            
            # Sazonalidade MMGD
            injecao_mensal = [row.get(f'ENE_MMGD_{i:02d}', 0) for i in range(1, 13)]
            meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
            df_mmgd = pd.DataFrame({'Mês': meses, 'Injeção (kWh)': injecao_mensal})
            fig_mmgd = px.bar(df_mmgd, x='Mês', y='Injeção (kWh)', title='Injeção Mensal MMGD')
            st.plotly_chart(fig_mmgd, use_container_width=True)
        else:
            st.info("Dados de MMGD não disponíveis para esta subestação.")
    except Exception as e:
        st.error(f"Erro ao renderizar dashboard: {e}")

def main():
    st.title("⚡ Big Data: LIGHT & ENEL RJ (Áreas Reais)")
    st.markdown("""
    Visualização de **Áreas Reais de Atendimento** com **Perfis de Consumo e Sazonalidade**.
    **Legenda Marcadores:** <span style='color:red'>●</span> LIGHT | <span style='color:blue'>●</span> ENEL
    """, unsafe_allow_html=True)
    
    if not os.path.exists(ARQUIVO_UNIFICADO):
        st.error(f"⚠️ Arquivo {ARQUIVO_UNIFICADO} não encontrado! Execute `python extrator.py` primeiro.")
        return
    
    with st.spinner("Carregando mapa e dados unificados..."):
        try:
            rj_shape, gdf_unificado, df_perfis, subestacoes_dict, id_to_nome, tree, ids = load_data()
            
            # Inicializar session state
            if 'selected_cod_id' not in st.session_state:
                st.session_state.selected_cod_id = None
            
            # Campo de Pesquisa
            opcoes = sorted([nome for nome in subestacoes_dict.keys() if nome])
            selected_nome = st.selectbox("Pesquisar Subestação:", options=[''] + opcoes, 
                                         index=0 if st.session_state.selected_cod_id is None else 
                                         (opcoes.index(id_to_nome[st.session_state.selected_cod_id]) + 1 if st.session_state.selected_cod_id in id_to_nome else 0))
            
            if selected_nome != '':
                new_cod_id = subestacoes_dict[selected_nome]
                if new_cod_id != st.session_state.selected_cod_id:
                    st.session_state.selected_cod_id = new_cod_id
            
            m = create_map_object(rj_shape, gdf_unificado, df_perfis)
            map_data = st_folium(m, width=1200, height=700, returned_objects=['last_clicked'], use_container_width=True)
            
            # Capturar clique no mapa
            if map_data and 'last_clicked' in map_data and map_data['last_clicked']:
                clicked_lat = map_data['last_clicked']['lat']
                clicked_lon = map_data['last_clicked']['lng']
                if tree is not None:
                    dist, idx = tree.query([clicked_lat, clicked_lon])
                    if dist < 0.001:  # Threshold para considerar como clique no marcador
                        new_cod_id = ids[idx]
                        if new_cod_id != st.session_state.selected_cod_id:
                            st.session_state.selected_cod_id = new_cod_id
                            st.experimental_rerun()
            
            # --- LEGENDA ABAIXO DO MAPA ---
            st.markdown("---")
            st.subheader("📖 Legenda do Mapa")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown("**Tipos de Subestação**")
                
                # Exibir ícones reais na legenda com HTML para controle total de proximidade
                def get_legend_html(icon_name, label):
                    b64 = get_image_base64(icon_name)
                    return f'''
                        <div style="display: flex; align-items: center; margin-bottom: 8px;">
                            <img src="{b64}" height="25" style="margin-right: 10px;">
                            <span style="font-size: 14px; font-weight: bold;">{label}</span>
                        </div>
                    '''
                st.markdown(get_legend_html("raio.png", "Distribuição Plena"), unsafe_allow_html=True)
                st.markdown(get_legend_html("satelite.png", "Distribuição Satélite"), unsafe_allow_html=True)
                st.markdown(get_legend_html("transformador.png", "Transformadora Pura"), unsafe_allow_html=True)
                st.markdown(get_legend_html("torre.png", "Transporte / Manobra"), unsafe_allow_html=True)
                
            with col2:
                st.markdown("**Tamanho do Ícone**")
                st.info("O tamanho do ícone é proporcional à **Potência Calculada** da subestação. Quanto maior o ícone, maior a capacidade de carga.")
                
            with col3:
                st.markdown("**Distribuidoras**")
                st.markdown("""
                - <span style='color:red'>●</span> **LIGHT**: Marcadores Vermelhos
                - <span style='color:blue'>●</span> **ENEL**: Marcadores Azuis
                """, unsafe_allow_html=True)
                
            with col4:
                st.markdown("**Camadas e Áreas**")
                st.write("Use o controle no canto superior direito do mapa para alternar a visibilidade das áreas de atendimento e da hierarquia de fluxo.")
            
            # --- DASHBOARD ABAIXO DAS LEGENDAS ---
            st.markdown("---")
            st.subheader("📊 Dashboard Detalhado da Subestação Selecionada")
            if st.session_state.selected_cod_id:
                render_dashboard(gdf_unificado, df_perfis, st.session_state.selected_cod_id, id_to_nome)
            else:
                st.info("Selecione uma subestação no mapa ou via pesquisa para exibir detalhes.")
        except Exception as e:
            st.error(f"Erro ao carregar mapa: {e}")
            st.exception(e)

if __name__ == "__main__":
    main()
