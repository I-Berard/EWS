from .base import DataSource
from .copernicus import CopernicusSource

# A factory or registry can be added here if multiple sources are implemented in the future
def get_data_source(source_name: str = "copernicus") -> DataSource:
    if source_name == "copernicus":
        return CopernicusSource()
    else:
        raise ValueError(f"Unknown data source: {source_name}")
