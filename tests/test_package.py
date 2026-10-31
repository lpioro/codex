import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.package_extension import package


class ExtensionPackage(unittest.TestCase):
    def test_reproducible_archive_and_manifest_references(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = package(Path(directory))
            original = archive.read_bytes()
            checksum = hashlib.sha256(original).hexdigest()
            self.assertEqual(archive.with_suffix('.zip.sha256').read_text(),
                             f'{checksum}  {archive.name}\n')
            with zipfile.ZipFile(archive) as bundle:
                manifest = json.loads(bundle.read('manifest.json'))
                referenced = [manifest['background']['service_worker'], manifest['options_page']]
                for script in manifest['content_scripts']:
                    referenced.extend(script['js'])
                self.assertTrue(set(referenced).issubset(bundle.namelist()))
                self.assertNotIn('.env', bundle.namelist())
            package(Path(directory))
            self.assertEqual(original, archive.read_bytes())

    def test_wrong_release_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                package(Path(directory), '999.0.0')
            self.assertEqual(list(Path(directory).iterdir()), [])
