import os
from unittest import TestCase

from crawler.spiders.gplay import AuthDb


class TestAuthDb(TestCase):
    def test_all(self):
        email = "test@example.org"
        ast = "astvalue"
        path = "test.db"
        try:
            auth_db = AuthDb(path)

            actual_ast = auth_db.get_ast(email)
            self.assertIsNone(actual_ast)

            auth_db.create_ast(email, ast)

            actual_ast = auth_db.get_ast(email)
            self.assertIsNotNone(actual_ast)

        finally:
            os.remove(path)
