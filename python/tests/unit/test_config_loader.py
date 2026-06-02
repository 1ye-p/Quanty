"""Tests for cquant.market_calendar.config_loader."""

import pytest

from cquant.market_calendar.config_loader import clear_config_cache, load_market_config


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_config_cache()
    yield
    clear_config_cache()


def test_load_cn_config():
    config = load_market_config("CN")
    assert config["market"] == "CN"
    assert config["price_limits"]["main_board"]["up"] == 0.10
    assert config["price_limits"]["st"]["up"] == 0.05
    assert config["settlement"] == "T+1"
    assert config["lot_size"] == 100
    assert config["adjustment"]["default"] == "forward"


def test_load_us_config():
    config = load_market_config("US")
    assert config["market"] == "US"
    assert config["price_limits"] == {}
    assert config["settlement"] == "T+2"


def test_load_hk_config():
    config = load_market_config("HK")
    assert config["market"] == "HK"
    assert config["lot_size"] == 100


def test_load_unknown_market_raises():
    with pytest.raises(FileNotFoundError):
        load_market_config("XX")


def test_case_insensitive():
    config = load_market_config("cn")
    assert config["market"] == "CN"


def test_cache_hit():
    config1 = load_market_config("CN")
    config2 = load_market_config("CN")
    assert config1 is config2
