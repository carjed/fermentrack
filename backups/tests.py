import json
import tarfile
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings

from app.models import BrewPiDevice
from backups.models import Backup


class BackupTests(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        backup_dir = Path(tmp.name)  # Starts empty, like a freshly mounted volume (no staging/ subdirectory)
        overrides = override_settings(BACKUP_DIR=backup_dir, BACKUP_STAGING_DIR=backup_dir / "staging")
        overrides.enable()
        self.addCleanup(overrides.disable)

    def test_exclude_list_skips_unknown_labels(self):
        with override_settings(BACKUPS_EXCLUDE_APPS=settings.BACKUPS_EXCLUDE_APPS + ['nope.Missing', 'nope']):
            excluded = Backup.get_exclude_list()
        self.assertIn('constance.Constance', excluded)
        # In-memory models have no table in older databases, so dumpdata must skip them
        for label in ('app.PinDevice', 'app.SensorDevice', 'app.BeerLogPoint'):
            self.assertIn(label, excluded)
        self.assertNotIn('nope.Missing', excluded)
        self.assertNotIn('nope', excluded)

    def test_perform_backup_creates_archive_without_site_settings(self):
        BrewPiDevice.objects.create(device_name='Chamber', temp_format='C')
        backup = Backup.objects.create()
        backup.perform_backup()

        with tarfile.open(backup.outfile_path) as archive:
            dump = json.load(archive.extractfile(settings.BACKUP_DATA_DUMP_FILE_NAME))
        models = {row['model'] for row in dump}
        self.assertIn('app.brewpidevice', models)
        self.assertFalse(any(m.startswith('constance.') for m in models))
