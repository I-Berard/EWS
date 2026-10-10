# Validation and Testing

## Test Suite
The platform includes an automated pytest suite in `tests/`:
- `test_synthetic.py`: Verifies deterministic generation of HDF5 files.
- `test_ingest.py`: Ensures HDF5 structure validation and loading logic is sound.
- `test_models.py`: Validates velocity calculation, robust residual handling (especially zero-MAD division errors), and change point detection algorithms.

To run tests:
```bash
source venv/bin/activate
pytest tests/
```

## Validation Limitations
- **Synthetic Data Performance != Real World Performance:** The anomalies present in the Demo mode are synthetic and idealized. Success on synthetic data does not guarantee similar performance on noisy, real-world InSAR time series affected by tropospheric delay or unwrapping errors.
- **Pending Ground-Truth Validation:** A rigorous evaluation of the proposed methods against Baseline A (Velocity Threshold) and Baseline B requires an independent, verified real-world landslide inventory over an area with high-quality InSAR coverage.
