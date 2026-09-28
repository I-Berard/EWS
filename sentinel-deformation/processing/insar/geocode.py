import os
import subprocess
import tempfile

SNAP_GEOCODE_GRAPH = """<graph id="Geocode">
  <version>1.0</version>
  <node id="Read">
    <operator>Read</operator>
    <sources/>
    <parameters><file>${input_dimap}</file></parameters>
  </node>
  
  <!-- Convert unwrapped phase to displacement (optional, can be done later in timeseries) -->
  <node id="PhaseToDisplacement">
    <operator>PhaseToDisplacement</operator>
    <sources><sourceProduct refid="Read"/></sources>
  </node>

  <!-- Terrain Correction for unwrapped phase/displacement -->
  <node id="Terrain-Correction">
    <operator>Terrain-Correction</operator>
    <sources><sourceProduct refid="PhaseToDisplacement"/></sources>
    <parameters>
      <sourceBands/>
      <demName>Copernicus 30m Global DEM</demName>
      <demResamplingMethod>BILINEAR_INTERPOLATION</demResamplingMethod>
      <imgResamplingMethod>BILINEAR_INTERPOLATION</imgResamplingMethod>
      <pixelSpacingInMeter>10.0</pixelSpacingInMeter>
      <mapProjection>WGS84(DD)</mapProjection>
      <nodataValueAtSea>true</nodataValueAtSea>
      <saveSelectedSourceBand>true</saveSelectedSourceBand>
    </parameters>
  </node>
  
  <node id="Write">
    <operator>Write</operator>
    <sources><sourceProduct refid="Terrain-Correction"/></sources>
    <parameters>
      <file>${output_tif}</file>
      <formatName>GeoTIFF-BigTIFF</formatName>
    </parameters>
  </node>
</graph>
"""

def geocode_unwrapped_phase(unwrapped_dimap: str, output_tif: str, gpt_path: str = "gpt"):
    """
    Applies terrain correction to Geocode the unwrapped interferogram and coherence map,
    and converts the unwrapped phase to Line-Of-Sight (LOS) displacement.
    """
    if not os.path.exists(unwrapped_dimap):
        raise FileNotFoundError(f"Input file not found: {unwrapped_dimap}")

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as temp_graph:
        temp_graph.write(SNAP_GEOCODE_GRAPH)
        graph_path = temp_graph.name
        
    print(f"Geocoding unwrapped phase {unwrapped_dimap}...")
    
    command = [
        gpt_path, graph_path,
        f"-Pinput_dimap={unwrapped_dimap}",
        f"-Poutput_tif={output_tif}"
    ]
    
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"Geocoded results saved to {output_tif}")
        return output_tif
    except subprocess.CalledProcessError as e:
        print(f"Error during geocoding: {e.stderr}")
        raise RuntimeError("Geocoding failed")
    finally:
        if os.path.exists(graph_path):
            os.remove(graph_path)
