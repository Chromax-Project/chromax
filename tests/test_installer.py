import io
import unittest
from chromax.common import ChromaxError
from chromax.installer import validate_target, find_device, digest_file


class InstallerTests(unittest.TestCase):
    def test_mounted_child_swap_and_readonly_are_rejected(self):
        for node in (
            {"type": "disk", "size": 4096, "children": [{"mountpoints": ["/"]}]},
            {"type": "disk", "size": 4096, "children": [{"mountpoints": ["[SWAP]"]}]},
            {"type": "disk", "size": 4096, "ro": True},
            {"type": "part", "size": 4096},
            {"type": "disk", "size": 10},
            None,
        ):
            with self.subTest(node=node), self.assertRaises(ChromaxError):
                validate_target(node, 1024)

    def test_unused_whole_disk_accepted(self):
        validate_target({"type": "disk", "size": 4096, "mountpoints": [None], "children": [{"mountpoints": [None]}]}, 1024)

    def test_target_lookup_is_exact(self):
        nodes = [{"name": "/dev/vda", "children": [{"name": "/dev/vda1"}]}]
        self.assertEqual(find_device(nodes, "/dev/vda1")["name"], "/dev/vda1")
        self.assertIsNone(find_device(nodes, "/dev/vd"))

    def test_digest_rewinds_stream(self):
        stream = io.BytesIO(b"abc")
        self.assertEqual(digest_file(stream), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        self.assertEqual(stream.tell(), 0)
