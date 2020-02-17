import sqlite3


class Db:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        c = self.conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS creds (email text, auth_sub_token text)")

    def load_creds(self):
        """
        Load Android accounts from local sqlite database
        Args:
            path: path to sqlite database

        Returns:
            list of accounts
        """
        c = self.conn.cursor()
        c.execute("SELECT * FROM creds")
        res = {}
        for email, auth_sub_token in c.fetchall():
            res[email] = auth_sub_token
        return res

    def set_token(self, email, auth_sub_token):
        c = self.conn.cursor()
        c.execute("INSERT INTO creds VALUES (?, ?)", (email, auth_sub_token))
        self.conn.commit()
