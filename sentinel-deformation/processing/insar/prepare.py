import os
import subprocess
import tempfile
from pathlib import Path

# Template for a SNAP gpt (Graph Processing Tool) XML graph
# This implements: Orbit Correction -> Thermal Noise Removal -> Calibration -> Terrain Correction
SNAP_PREPROCESSING_GRAPH = """<graph id="Graph">
  <version>1.0</version>
  <node id="Read">
    <operator>Read</operator>
    <sources/>
    <parameters class="com.bc.ceres.binding.dom.XppDomElement">
      <file>${input_file}</file>
    </parameters>
  </node>
  <node id="Apply-Orbit-File">
    <operator>Apply-Orbit-File</operator>
    <sources>
      <sourceProduct refid="Read"/>
    </sources>
    <parameters class="com.bc.ceres.binding.dom.XppDomElement">
      <orbitType>Sentinel Precise (Auto Download)</orbitType>
      <polyDegree>3</polyDegree>
      <continueOnFail>true</continueOnFail>
    </parameters>
  </node>
  <node id="ThermalNoiseRemoval">
    <operator>ThermalNoiseRemoval</operator>
    <sources>
      <sourceProduct refid="Apply-Orbit-File"/>
    </sources>
    <parameters class="com.bc.ceres.binding.dom.XppDomElement">
      <selectedPolarisations>VV,VH</selectedPolarisations>
      <removeThermalNoise>true</removeThermalNoise>
      <reIntroduceThermalNoise>false</reIntroduceThermalNoise>
    </parameters>
  </node>
  <node id="Calibration">
    <operator>Calibration</operator>
    <sources>
      <sourceProduct refid="ThermalNoiseRemoval"/>
    </sources>
    <parameters class="com.bc.ceres.binding.dom.XppDomElement">
      <sourceBands/>
      <auxFile>Product Auxiliary File</auxFile>
      <externalAuxFile/>
      <outputImageInComplex>false</outputImageInComplex>
      <outputImageScaleInDb>false</outputImageScaleInDb>
      <createGammaBand>false</createGammaBand>
      <createBetaBand>false</createBetaBand>
      <selectedPolarisations>VV,VH</selectedPolarisations>
      <outputSigmaBand>true</outputSigmaBand>
      <outputGammaBand>false</outputGammaBand>
      <outputBetaBand>false</outputBetaBand>
    </parameters>
  </node>
  <node id="Terrain-Correction">
    <operator>Terrain-Correction</operator>
    <sources>
      <sourceProduct refid="Calibration"/>
    </sources>
    <parameters class="com.bc.ceres.binding.dom.XppDomElement">
      <sourceBands/>
      <demName>Copernicus 30m Global DEM</demName>
      <externalDEMFile/>
      <externalDEMNoDataValue>0.0</externalDEMNoDataValue>
      <externalDEMApplyEGM>true</externalDEMApplyEGM>
      <demResamplingMethod>BILINEAR_INTERPOLATION</demResamplingMethod>
      <imgResamplingMethod>BILINEAR_INTERPOLATION</imgResamplingMethod>
      <pixelSpacingInMeter>10.0</pixelSpacingInMeter>
      <pixelSpacingInDegree>8.983152841195215E-5</pixelSpacingInDegree>
      <mapProjection>WGS84(DD)</mapProjection>
      <alignToStandardGrid>false</alignToStandardGrid>
      <standardGridOriginX>0.0</standardGridOriginX>
      <standardGridOriginY>0.0</standardGridOriginY>
      <nodataValueAtSea>true</nodataValueAtSea>
      <saveDEM>false</saveDEM>
      <saveLatLon>false</saveLatLon>
      <saveIncidenceAngleFromDEM>false</saveIncidenceAngleFromDEM>
      <saveLocalIncidenceAngle>false</saveLocalIncidenceAngle>
      <saveProjectedLocalIncidenceAngle>false</saveProjectedLocalIncidenceAngle>
      <saveSelectedSourceBand>true</saveSelectedSourceBand>
      <outputComplex>false</outputComplex>
      <applyRadiometricNormalization>false</applyRadiometricNormalization>
      <saveSigmaNought>false</saveSigmaNought>
      <saveGammaNought>false</saveGammaNought>
      <saveBetaNought>false</saveBetaNought>
      <incidenceAngleForSigma0>Use projected local incidence angle from DEM</incidenceAngleForSigma0>
      <incidenceAngleForGamma0>Use projected local incidence angle from DEM</incidenceAngleForGamma0>
      <auxFile>Latest Auxiliary File</auxFile>
      <externalAuxFile/>
    </parameters>
  </node>
  <node id="Write">
    <operator>Write</operator>
    <sources>
      <sourceProduct refid="Terrain-Correction"/>
    </sources>
    <parameters class="com.bc.ceres.binding.dom.XppDomElement">
      <file>${output_file}</file>
      <formatName>GeoTIFF-BigTIFF</formatName>
    </parameters>
  </node>
</graph>
"""

def preprocess_sentinel1_intensity(input_zip_path: str, output_tif_path: str, gpt_path: str = "gpt"):
    """
    Runs the SNAP Graph Processing Tool (gpt) to preprocess a Sentinel-1 product.
    Note: This is an Intensity/Amplitude pipeline. For InSAR (SLCs), terrain correction 
    is typically performed later in the pipeline after interferogram generation and unwrapping.
    """
    
    if not os.path.exists(input_zip_path):
        raise FileNotFoundError(f"Input file not found: {input_zip_path}")
        
    # Create a temporary XML file for the graph
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as temp_graph:
        temp_graph.write(SNAP_PREPROCESSING_GRAPH)
        graph_path = temp_graph.name
        
    print(f"Running preprocessing on {input_zip_path}...")
    
    # Build the gpt command
    command = [
        gpt_path,
        graph_path,
        f"-Pinput_file={input_zip_path}",
        f"-Poutput_file={output_tif_path}",
        # Memory optimization flags for gpt
        "-q", "8", # max CPU threads
        "-c", "4G" # Cache size
    ]
    
    try:
        process = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print("Preprocessing completed successfully.")
        return output_tif_path
    except subprocess.CalledProcessError as e:
        print(f"Error during preprocessing: {e.stderr}")
        raise RuntimeError("SNAP gpt preprocessing failed")
    finally:
        # Cleanup the temporary graph XML
        if os.path.exists(graph_path):
            os.remove(graph_path)

if __name__ == "__main__":
    # Example usage
    # preprocess_sentinel1_intensity("S1A_IW_GRDH_...zip", "output_preprocessed.tif")
    pass
