import json
import logging

from requests_mock import Mocker
from ska_sdp_dataproduct_metadata import MetaData

from ska_dlm import CONFIG, dlm_ingest


def test_notify_data_dashboard(caplog):
    """Test that the write hook will post metadata file info to a URL."""
    # mock a response for this URL, a copy of the normal response from ska-sdp-dataproduct-api
    with Mocker() as req_mock:
        assert isinstance(req_mock, Mocker)
        req_mock.post(
            CONFIG.DATA_PRODUCT_API.url + "/ingestnewmetadata",
            text="New data product metadata file loaded and store index updated",
            status_code=200,
        )
        dlm_ingest.notify_data_dashboard(json.dumps({"execution_block": "block123"}))

    assert not any(record.levelno == logging.ERROR for record in caplog.records), caplog.text


def test_notify_data_dashboard_http_errors(caplog):
    """Test that the write hook will post metadata file info to a URL."""
    with Mocker() as req_mock:
        assert isinstance(req_mock, Mocker)
        req_mock.post(CONFIG.DATA_PRODUCT_API.url + "/ingestnewmetadata", status_code=404)
        dlm_ingest.notify_data_dashboard(MetaData())

    assert any(record.levelno == logging.ERROR for record in caplog.records), caplog.text
