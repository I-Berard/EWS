from abc import ABC, abstractmethod
from typing import Dict, Any, List

class DataSource(ABC):
    """
    Abstract base class for all satellite data sources.
    This modular design allows adding new data sources easily.
    """
    @abstractmethod
    def search(self, bbox: list, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Search for data acquisitions.
        
        Args:
            bbox: [min_lon, min_lat, max_lon, max_lat]
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            
        Returns:
            List of dictionaries containing metadata for each found product.
        """
        pass
        
    @abstractmethod
    def download(self, product_id: str, output_dir: str) -> str:
        """
        Download a specific product.
        
        Args:
            product_id: The unique identifier of the product.
            output_dir: Directory where the product will be downloaded.
            
        Returns:
            The filepath of the downloaded product.
        """
        pass
