import osmnx as ox
import networkx as nx
import streamlit as st
import folium
import geopandas as gpd
from folium.plugins import Draw
from streamlit_folium import st_folium
from shapely.geometry import shape 

# 1. CONFIGURAÇÃO DE CARREGAMENTO OTIMIZADO (BACKEND)
@st.cache_resource
def load_graph():
    return ox.load_graphml("cwb_streets.graphml")

@st.cache_data
def load_buildings():
    gdf = gpd.read_parquet("cwb_buildings.parquet")
    gdf = gdf[['geometry']].copy()
    gdf['uid'] = [str(i) for i in range(len(gdf))]
    return gdf

# Inicializa o grafo e os dados de edificações
drive_graph = load_graph()
buildings_gdf = load_buildings()

# Coordenadas centrais de Curitiba
center_lat = -25.4300
center_lng = -49.2711

st.set_page_config(page_title="Roteirizador Web Otimizado", layout="wide")

st.title("🗺️ Mapas e suas funcionalidades.")
st.markdown("Use a ferramenta de **Desenho (Polígono ou Retângulo)** no menu esquerdo do mapa para renderizar as edificações de uma região.")

# 2. INICIALIZAÇÃO DO ESTADO DA SESSÃO
if 'start_coords' not in st.session_state: st.session_state.start_coords = None
if 'end_coords' not in st.session_state: st.session_state.end_coords = None
if 'route_coords' not in st.session_state: st.session_state.route_coords = None
if 'selected_buildings' not in st.session_state: st.session_state.selected_buildings = set()
# Variável para armazenar a área geométrica desenhada pelo usuário
if 'drawn_area' not in st.session_state: st.session_state.drawn_area = None

# 3. FUNÇÃO DE ESTILO DINÂMICO PARA AS EDIFICAÇÕES
def get_dynamic_style(feature):
    building_id = feature['properties']['uid']
    if building_id in st.session_state.selected_buildings:
        return {'fillColor': '#ff0000', 'color': '#8b0000', 'weight': 2, 'fillOpacity': 0.8} # Vermelho se selecionado
    return {'fillColor': '#808080', 'color': '#2a2a2a', 'weight': 1, 'fillOpacity': 0.5}     # Cinza padrão

# 4. BARRA LATERAL (ENTRADAS DE TEXTO E CONTROLES)
with st.sidebar:
    st.header("📌 Configurações de Trajeto")
    address_start = st.text_input("Origem (Texto)", value="Rua XV, Curitiba, Paraná, Brazil")
    address_end = st.text_input("Destino (Texto)", value="PUCPR, Curitiba, Paraná, Brazil")

    if st.button("Buscar Rota (Por Texto)", use_container_width=True):
        with st.spinner("Geocodificando endereços e calculando rota..."):
            try:
                lat_start, lng_start = ox.geocode(address_start)
                lat_end, lng_end = ox.geocode(address_end)

                st.session_state.start_coords = {'lat': lat_start, 'lng': lng_start}
                st.session_state.end_coords = {'lat': lat_end, 'lng': lng_end}
                
                node_start = ox.distance.nearest_nodes(drive_graph, X=lng_start, Y=lat_start)
                node_end = ox.distance.nearest_nodes(drive_graph, X=lng_end, Y=lat_end)
                
                calculated_route = nx.shortest_path(drive_graph, node_start, node_end, weight='length')
                st.session_state.route_coords = [(drive_graph.nodes[n]['y'], drive_graph.nodes[n]['x']) for n in calculated_route]
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao buscar os endereços: {e}")
    
    st.markdown("---")
    
    if st.button("Calcular Rota por Cliques", use_container_width=True):
        if st.session_state.start_coords and st.session_state.end_coords:
            with st.spinner("Calculando rota pelos pontos clicados..."):
                node_start = ox.distance.nearest_nodes(drive_graph, X=st.session_state.start_coords['lng'], Y=st.session_state.start_coords['lat'])
                node_end = ox.distance.nearest_nodes(drive_graph, X=st.session_state.end_coords['lng'], Y=st.session_state.end_coords['lat'])
                
                calculated_route = nx.shortest_path(drive_graph, node_start, node_end, weight='length')
                st.session_state.route_coords = [(drive_graph.nodes[n]['y'], drive_graph.nodes[n]['x']) for n in calculated_route]
                st.rerun()
        else:
            st.warning("Clique no mapa para definir a Origem e o Destino primeiro!")

    if st.button("Limpar Tudo", use_container_width=True):
        st.session_state.start_coords = None
        st.session_state.end_coords = None
        st.session_state.route_coords = None
        st.session_state.selected_buildings = set()
        st.session_state.drawn_area = None
        st.rerun()

# 5. CONSTRUÇÃO DO MAPA BASE DO FOLIUM
map_object = folium.Map(location=[center_lat, center_lng], zoom_start=14)

# APLICAÇÃO DO FILTRO ESPACIAL: Só adiciona prédios se houver uma área desenhada na tela
if st.session_state.drawn_area:
    # Converte o JSON da área desenhada em um polígono geométrico utilizável pelo Geopandas
    spatial_filter = shape(st.session_state.drawn_area)
    
    with st.spinner("Filtrando edificações na região selecionada..."):
        # Corta o DataFrame original mantendo apenas as geometrias que cruzam a área desenhada
        filtered_buildings = buildings_gdf[buildings_gdf.intersects(spatial_filter)]
        
        # Desenha no mapa estritamente as edificações filtradas (Reduz de 100k para poucas dezenas)
        folium.GeoJson(
            filtered_buildings,
            name="Edificações Filtradas",
            style_function=get_dynamic_style,
            highlight_function=lambda x: {'weight': 3, 'color': '#0000ff', 'fillOpacity': 0.7}
        ).add_to(map_object)
        
        st.sidebar.metric(label="Prédios Renderizados", value=len(filtered_buildings))

# Adiciona os marcadores visuais de Origem e Destino se existirem
if st.session_state.start_coords:
    folium.Marker([st.session_state.start_coords['lat'], st.session_state.start_coords['lng']], popup="Origem", icon=folium.Icon(color="green", icon="play")).add_to(map_object)

if st.session_state.end_coords:
    folium.Marker([st.session_state.end_coords['lat'], st.session_state.end_coords['lng']], popup="Destino", icon=folium.Icon(color="red", icon="flag")).add_to(map_object)

# Adiciona a linha estrutural da rota se calculada
if st.session_state.route_coords:
    folium.PolyLine(st.session_state.route_coords, color="blue", weight=5, opacity=0.8).add_to(map_object)

# Adiciona e configura a barra de ferramentas de desenho no mapa
Draw(
    export=False,
    position="topleft",
    draw_options={
        "polyline": False, "circlemarker": False, "marker": False, "circle": False,
        "polygon": True, "rectangle": True
    }
).add_to(map_object)

# 6. RENDERIZAÇÃO E MONITORAMENTO DE EVENTOS DO MAPA
map_rendered = st_folium(
    map_object, 
    width=1000, 
    height=450,
    returned_objects=["last_active_drawing", "last_clicked"]
)

# 7. PROCESSAMENTO DOS EVENTOS CAPTURADOS
# Fluxo A: Usuário desenhou ou clicou em uma estrutura existente
if map_rendered.get("last_active_drawing"):
    active_geometry = map_rendered["last_active_drawing"]["geometry"]
    active_properties = map_rendered["last_active_drawing"]["properties"]
    
    # Se a estrutura possui um 'uid', significa que o usuário clicou em um prédio já filtrado para selecioná-lo
    if "uid" in active_properties:
        building_uid = active_properties["uid"]
        if building_uid in st.session_state.selected_buildings:
            st.session_state.selected_buildings.remove(building_uid)
        else:
            st.session_state.selected_buildings.add(building_uid)
        st.rerun()
    
    # Se não possui 'uid', significa que é um novo polígono/retângulo de filtro que o usuário acabou de desenhar
    else:
        if st.session_state.drawn_area != active_geometry:
            st.session_state.drawn_area = active_geometry
            st.rerun()

# Fluxo B: Usuário deu um clique seco em um ponto limpo do mapa para traçar rotas
elif map_rendered.get("last_clicked"):
    click_coords = map_rendered["last_clicked"]
    
    if st.session_state.start_coords is None:
        st.session_state.start_coords = click_coords
        st.rerun()
    elif st.session_state.end_coords is None and click_coords != st.session_state.start_coords:
        st.session_state.end_coords = click_coords
        st.rerun()