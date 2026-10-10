import os
import pytest
import h5py
import numpy as np
from core.data.validation import validate_h5_structure
from core.data.ingest import load_mintpy_timeseries

@pytest.fixture
def mock_h5_file(tmp_path):
    filepath = os.path.join(tmp_path, "test.h5")
    with h5py.File(filepath, 'w') as f:
        f.create_dataset('date', data=[b'20230101', b'20230113'])
        f.create_dataset('timeseries', data=np.zeros((2, 10, 10)))
        f.attrs['UNIT'] = 'm'
        f.attrs['X_FIRST'] = 0.0
        f.attrs['Y_FIRST'] = 0.0
    return filepath

def test_validation(mock_h5_file):
    is_valid, msg = validate_h5_structure(mock_h5_file)
    assert is_valid

def test_ingest(mock_h5_file):
    dates, timeseries, metadata = load_mintpy_timeseries(mock_h5_file)
    assert len(dates) == 2
    assert timeseries.shape == (2, 10, 10)
    assert metadata["UNIT"] == "m"

