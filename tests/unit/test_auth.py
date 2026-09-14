import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

import pytest
from auth.passwords import PasswordHasher


class TestPasswordHashing:
    def setup_method(self):
        self.hasher = PasswordHasher()

    def test_hash_password(self):
        password = "SecurePass123!"
        hashed = self.hasher.hash(password)
        assert hashed != password
        assert len(hashed) > 20

    def test_verify_correct_password(self):
        password = "SecurePass123!"
        hashed = self.hasher.hash(password)
        assert self.hasher.verify(hashed, password) is True

    def test_verify_wrong_password(self):
        password = "SecurePass123!"
        hashed = self.hasher.hash(password)
        assert self.hasher.verify(hashed, "WrongPass") is False

    def test_different_hashes_same_password(self):
        password = "SecurePass123!"
        hash1 = self.hasher.hash(password)
        hash2 = self.hasher.hash(password)
        assert hash1 != hash2  # salted

    def test_empty_password_still_hashes(self):
        hashed = self.hasher.hash("")
        assert hashed != ""
