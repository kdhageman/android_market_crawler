import shutil
import tempfile
import unittest
import os

from scripts.remove_dirs import remove_dirs


class RemoveDirsTest(unittest.TestCase):
    def setUp(self):
        self.rootdir = tempfile.mkdtemp()

    def test_remove_dirs(self):
        dirnames = [os.path.join(self.rootdir, d) for d in ["a", "b", "c"]]
        for d in dirnames:
            os.mkdir(d)

        # we expect three directories to exist
        _, dirs, _ = next(os.walk(self.rootdir))
        self.assertEqual(len(dirs), 3)

        remove_dirs(dirnames)

        # we expect zero directories to exist
        _, dirs, _ = next(os.walk(self.rootdir))
        self.assertEqual(len(dirs), 0)

    def tearDown(self):
        shutil.rmtree(self.rootdir)


if __name__ == '__main__':
    unittest.main()
