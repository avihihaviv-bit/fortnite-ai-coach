import keyring
import pytest
from keyring.backends import fail

from fortnite_coach.ai.key_store import KeyStore, KeyStoreError, mask, validate_key_format
from fortnite_coach.ai.status import GeminiStatus, current_status

FAKE_KEY = "AIza" + "T" * 35  # TEST DATA: not a real key


def test_format_validation():
    assert validate_key_format(f"  {FAKE_KEY}\n") == FAKE_KEY
    for bad in ("", "   ", "short", "has space inside the key value!!", "x" * 300):
        with pytest.raises(KeyStoreError):
            validate_key_format(bad)


def test_save_load_delete(memory_keyring):
    ks = KeyStore()
    assert not ks.has_key()
    ks.save(FAKE_KEY)
    assert ks.load() == FAKE_KEY and ks.has_key()
    ks.delete()
    assert not ks.has_key()
    ks.delete()  # deleting twice is harmless


def test_no_secure_backend_means_not_saved():
    keyring.set_keyring(fail.Keyring())
    ks = KeyStore()
    with pytest.raises(KeyStoreError) as e:
        ks.save(FAKE_KEY)
    assert e.value.i18n_key == "apikey.err_no_backend"


def test_mask_hides_key():
    assert FAKE_KEY not in mask(FAKE_KEY) and mask(FAKE_KEY).endswith(FAKE_KEY[-4:])


def test_status_from_facts():
    assert current_status(False) is GeminiStatus.NOT_CONFIGURED
    assert current_status(True) is GeminiStatus.CONFIGURED_UNTESTED
    assert not GeminiStatus.CONFIGURED_UNTESTED.can_analyze
