"""Build a reproducible extension ZIP; include only explicitly listed files."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ('manifest.json', 'background.js', 'content.js', 'options.html', 'options.js')


def package(output, expected_version=None):
    manifest = json.loads((ROOT / 'extension/manifest.json').read_text())
    version = manifest['version']
    if expected_version and expected_version != version:
        raise ValueError(f'Tag version {expected_version} differs from manifest {version}')
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'prompt-observatory-extension-{version}.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for filename in FILES:
            entry = zipfile.ZipInfo(filename, date_time=(2020, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            bundle.writestr(entry, (ROOT / 'extension' / filename).read_bytes())
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert set(bundle.namelist()) == set(FILES)
        assert json.loads(bundle.read('manifest.json'))['version'] == version
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n')
    print(archive)
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    parser.add_argument('--version', help='Expected manifest version, without v prefix')
    args = parser.parse_args()
    package(args.output, args.version)
