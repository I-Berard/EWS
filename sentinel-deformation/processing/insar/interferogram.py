import os
import subprocess
import tempfile

# Template for Sentinel-1 TOPS InSAR Coregistration and Interferogram generation
# Includes: Read Master/Slave -> Split -> Apply Orbits -> Back-Geocoding -> ESD -> Interferogram -> Deburst -> TopoPhaseRemoval
SNAP_INSAR_GRAPH = """<graph id="InSAR_Pipeline">
  <version>1.0</version>
  <!-- Master Image -->
  <node id="Read-Master">
    <operator>Read</operator>
    <sources/>
    <parameters><file>${master_file}</file></parameters>
  </node>
  <!-- Slave Image -->
  <node id="Read-Slave">
    <operator>Read</operator>
    <sources/>
    <parameters><file>${slave_file}</file></parameters>
  </node>
  
  <!-- TOPS Split Master -->
  <node id="TOPSAR-Split-Master">
    <operator>TOPSAR-Split</operator>
    <sources><sourceProduct refid="Read-Master"/></sources>
    <parameters>
      <subswath>${subswath}</subswath>
      <selectedPolarisations>VV</selectedPolarisations>
    </parameters>
  </node>
  
  <!-- TOPS Split Slave -->
  <node id="TOPSAR-Split-Slave">
    <operator>TOPSAR-Split</operator>
    <sources><sourceProduct refid="Read-Slave"/></sources>
    <parameters>
      <subswath>${subswath}</subswath>
      <selectedPolarisations>VV</selectedPolarisations>
    </parameters>
  </node>

  <!-- Apply Orbits Master -->
  <node id="Apply-Orbit-Master">
    <operator>Apply-Orbit-File</operator>
    <sources><sourceProduct refid="TOPSAR-Split-Master"/></sources>
    <parameters><orbitType>Sentinel Precise (Auto Download)</orbitType></parameters>
  </node>

  <!-- Apply Orbits Slave -->
  <node id="Apply-Orbit-Slave">
    <operator>Apply-Orbit-File</operator>
    <sources><sourceProduct refid="TOPSAR-Split-Slave"/></sources>
    <parameters><orbitType>Sentinel Precise (Auto Download)</orbitType></parameters>
  </node>

  <!-- Coregistration (Back-Geocoding) -->
  <node id="Back-Geocoding">
    <operator>Back-Geocoding</operator>
    <sources>
      <sourceProduct refid="Apply-Orbit-Master"/>
      <sourceProduct.1 refid="Apply-Orbit-Slave"/>
    </sources>
    <parameters>
      <demName>Copernicus 30m Global DEM</demName>
      <demResamplingMethod>BILINEAR_INTERPOLATION</demResamplingMethod>
      <resamplingType>BISINC_5_POINT_INTERPOLATION</resamplingType>
    </parameters>
  </node>
  
  <!-- Enhanced Spectral Diversity (ESD) for accurate azimuth coregistration -->
  <node id="Enhanced-Spectral-Diversity">
    <operator>Enhanced-Spectral-Diversity</operator>
    <sources><sourceProduct refid="Back-Geocoding"/></sources>
  </node>

  <!-- Interferogram and Coherence -->
  <node id="Interferogram">
    <operator>Interferogram</operator>
    <sources><sourceProduct refid="Enhanced-Spectral-Diversity"/></sources>
    <parameters>
      <subtractFlatEarthPhase>true</subtractFlatEarthPhase>
      <srpPolynomialDegree>5</srpPolynomialDegree>
      <srpNumberPoints>501</srpNumberPoints>
      <orbitDegree>3</orbitDegree>
      <includeCoherence>true</includeCoherence>
      <squarePixel>true</squarePixel>
    </parameters>
  </node>

  <!-- TOPS Deburst -->
  <node id="TOPSAR-Deburst">
    <operator>TOPSAR-Deburst</operator>
    <sources><sourceProduct refid="Interferogram"/></sources>
  </node>

  <!-- Topographic Phase Removal -->
  <node id="TopoPhaseRemoval">
    <operator>TopoPhaseRemoval</operator>
    <sources><sourceProduct refid="TOPSAR-Deburst"/></sources>
    <parameters>
      <demName>Copernicus 30m Global DEM</demName>
    </parameters>
  </node>
  
  <!-- Multilooking to reduce speckle (optional but recommended before unwrapping) -->
  <node id="Multilook">
    <operator>Multilook</operator>
    <sources><sourceProduct refid="TopoPhaseRemoval"/></sources>
    <parameters>
      <nRgLooks>4</nRgLooks>
      <nAzLooks>1</nAzLooks>
      <outputIntensity>false</outputIntensity>
    </parameters>
  </node>
  
  <!-- Phase Filtering (Goldstein) -->
  <node id="GoldsteinPhaseFiltering">
    <operator>GoldsteinPhaseFiltering</operator>
    <sources><sourceProduct refid="Multilook"/></sources>
    <parameters>
      <alpha>1.0</alpha>
      <FFTSizeString>64</FFTSizeString>
      <windowSizeString>3</windowSizeString>
    </parameters>
  </node>

  <!-- Write Output -->
  <node id="Write">
    <operator>Write</operator>
    <sources><sourceProduct refid="GoldsteinPhaseFiltering"/></sources>
    <parameters>
      <file>${output_file}</file>
      <formatName>BEAM-DIMAP</formatName>
    </parameters>
  </node>
</graph>
"""

def generate_interferogram(master_zip: str, slave_zip: str, output_dimap: str, subswath: str = "IW2", gpt_path: str = "gpt"):
    """
    Coregisters two Sentinel-1 SLC images, generates a flattened and filtered interferogram,
    and calculates coherence.
    
    Args:
        master_zip: Path to master Sentinel-1 SLC zip file.
        slave_zip: Path to slave Sentinel-1 SLC zip file.
        output_dimap: Path to output BEAM-DIMAP format file (.dim).
        subswath: Subswath to process (e.g., IW1, IW2, IW3).
    """
    if not os.path.exists(master_zip):
        raise FileNotFoundError(f"Master file not found: {master_zip}")
    if not os.path.exists(slave_zip):
        raise FileNotFoundError(f"Slave file not found: {slave_zip}")

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as temp_graph:
        temp_graph.write(SNAP_INSAR_GRAPH)
        graph_path = temp_graph.name
        
    print(f"Generating Interferogram: Master={master_zip} | Slave={slave_zip} | Subswath={subswath}")
    
    command = [
        gpt_path, graph_path,
        f"-Pmaster_file={master_zip}",
        f"-Pslave_file={slave_zip}",
        f"-Psubswath={subswath}",
        f"-Poutput_file={output_dimap}",
        "-q", "8", "-c", "6G" # Allocate sufficient memory for InSAR
    ]
    
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"Interferogram successfully saved to {output_dimap}")
        return output_dimap
    except subprocess.CalledProcessError as e:
        print(f"Error during interferogram generation: {e.stderr}")
        raise RuntimeError("Interferogram generation failed")
    finally:
        if os.path.exists(graph_path):
            os.remove(graph_path)
