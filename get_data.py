
import osmnx as ox
from pathlib import Path


def get_street_graphs(locate: str, file_path: Path, network_type: str = "drive"):

    drive_graph = ox.graph_from_place(locate, network_type)

    ox.save_graphml(drive_graph, file_path)



def get_features_place_gdf(locate: str, file_path: Path, tags: dict = {"building": True}):
        
    features = ox.features_from_place(locate, tags)
    
    print(f"Salvando {len(features)} elementos em: {file_path}")
    
    for col in features.columns:
        if features[col].apply(lambda x: isinstance(x, (list, dict))).any():
            features[col] = features[col].astype(str)
            
    features.to_parquet(file_path)


get_features_place_gdf(locate="Xaxim, Curitiba, Paraná, Brazil", file_path= Path("cwb_buildings.parquet"))
