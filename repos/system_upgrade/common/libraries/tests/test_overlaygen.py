import os

import pytest

from leapp.libraries.common import overlaygen
from leapp.libraries.common.testutils import CurrentActorMocked, logger_mocked
from leapp.libraries.stdlib import api
from leapp.models import FstabEntry, StorageInfo


def make_storage_info(mountpoints):
    entries = [
        FstabEntry(
            fs_spec='/dev/sda1',
            fs_file=mp,
            fs_vfstype='ext4',
            fs_mntops='defaults',
            fs_freq='0',
            fs_passno='0',
        )
        for mp in mountpoints
    ]
    return StorageInfo(fstab=entries)


class TestGetMaxDiskimageSizeMibs(object):
    def test_returns_correct_value_for_ext4_filesizebits(self, monkeypatch):
        # ext4 with 4K blocks reports 44 bits -> max 2^44 - 1 bytes -> 16,777,215 MiB
        monkeypatch.setattr(os, 'pathconf', lambda path, name: 44)
        result = overlaygen._get_max_diskimage_size_mibs('/some/dir')
        assert result == (2 ** 44 - 1) // (1024 * 1024)
        assert result == 16777215

    def test_returns_correct_value_for_xfs_filesizebits(self, monkeypatch):
        # XFS reports 63 bits -> max 2^63 - 1 bytes
        monkeypatch.setattr(os, 'pathconf', lambda path, name: 63)
        result = overlaygen._get_max_diskimage_size_mibs('/some/dir')
        assert result == (2 ** 63 - 1) // (1024 * 1024)

    def test_returns_none_on_oserror(self, monkeypatch):
        def raise_oserror(path, name):
            raise OSError('not supported')

        monkeypatch.setattr(os, 'pathconf', raise_oserror)
        monkeypatch.setattr(api, 'current_actor', CurrentActorMocked())
        result = overlaygen._get_max_diskimage_size_mibs('/some/dir')
        assert result is None

    def test_returns_none_when_pathconf_missing(self, monkeypatch):
        monkeypatch.setattr(api, 'current_actor', CurrentActorMocked())
        # Simulate AttributeError by making pathconf raise it
        monkeypatch.setattr(os, 'pathconf', lambda path, name: (_ for _ in ()).throw(AttributeError()))
        result = overlaygen._get_max_diskimage_size_mibs('/some/dir')
        assert result is None


class TestPrepareRequiredMountsCapsDiskSize(object):
    """Verify that _prepare_required_mounts caps disk image size to the filesystem limit."""

    def _setup_mocks(self, monkeypatch, tmp_path, free_space_by_path, max_image_size_mibs):
        """Common mock setup. Returns (scratch_dir, mounts_dir, created_images dict)."""
        scratch_dir = str(tmp_path / 'scratch')
        mounts_dir = str(tmp_path / 'mounts')
        os.makedirs(scratch_dir)
        os.makedirs(mounts_dir)
        created_images = {}

        def fake_get_fspace(path, convert_to_mibs=False, coefficient=1):
            size = free_space_by_path.get(path, 10240)
            return int(size * coefficient)

        def fake_get_max(directory):
            return max_image_size_mibs

        def fake_create_diskimages_dir(sd, diskimages_dir):
            os.makedirs(diskimages_dir, exist_ok=True)

        def fake_ensure_space(space_needed, directory):
            pass

        def fake_run(cmd):
            pass

        def fake_create_mount_disk_image(disk_images_directory, path, disk_size):
            created_images[path] = disk_size
            image_path = os.path.join(disk_images_directory, 'root' + path.replace('/', '_'))
            open(image_path, 'w').close()
            return image_path

        monkeypatch.setattr(overlaygen, '_get_fspace', fake_get_fspace)
        monkeypatch.setattr(overlaygen, '_get_max_diskimage_size_mibs', fake_get_max)
        monkeypatch.setattr(overlaygen, '_create_diskimages_dir', fake_create_diskimages_dir)
        monkeypatch.setattr(overlaygen, '_ensure_enough_diskimage_space', fake_ensure_space)
        monkeypatch.setattr(overlaygen, '_create_mount_disk_image', fake_create_mount_disk_image)
        monkeypatch.setattr(overlaygen, 'run', fake_run)
        monkeypatch.setattr(api, 'current_actor', CurrentActorMocked())

        return scratch_dir, mounts_dir, created_images

    def test_disk_size_capped_when_exceeds_fs_limit(self, monkeypatch, tmp_path):
        """When /home free space exceeds the FS file size limit, the disk image is capped."""
        # Simulate CL7 cPanel server: / on ext4 (142 GiB free), /home on large SAN (19 TB free)
        ext4_limit_mibs = 16777215  # 2^44 - 1 MiB (ext4 with 4K blocks)
        scratch_dir = str(tmp_path / 'scratch')

        free_space = {
            '/': 145408,
            '/home': 19373090,  # ~19 TB - exceeds ext4 limit
            scratch_dir: 145408,
        }

        scratch_dir, mounts_dir, created_images = self._setup_mocks(
            monkeypatch, tmp_path, free_space, ext4_limit_mibs
        )

        storage_info = make_storage_info(['/', '/home'])
        overlaygen._prepare_required_mounts(scratch_dir, mounts_dir, storage_info, scratch_reserve=0)

        assert created_images['/home'] == ext4_limit_mibs, (
            '/home disk image must be capped to ext4 file size limit'
        )
        assert created_images['/'] <= ext4_limit_mibs

    def test_disk_size_not_capped_when_within_fs_limit(self, monkeypatch, tmp_path):
        """When free space is within the FS limit, the disk image size is kept as-is."""
        ext4_limit_mibs = 16777215
        scratch_dir = str(tmp_path / 'scratch')

        free_space = {
            '/': 145408,
            '/home': 200000,  # 200 GiB - well within ext4 limit
            scratch_dir: 145408,
        }

        scratch_dir, mounts_dir, created_images = self._setup_mocks(
            monkeypatch, tmp_path, free_space, ext4_limit_mibs
        )

        storage_info = make_storage_info(['/', '/home'])
        overlaygen._prepare_required_mounts(scratch_dir, mounts_dir, storage_info, scratch_reserve=0)

        # /home is within limit: 95% of 200000 = 190000
        assert created_images['/home'] == int(200000 * 0.95)

    def test_disk_size_not_capped_when_fs_limit_unknown(self, monkeypatch, tmp_path):
        """When the FS limit cannot be determined (None), disk sizes are passed through unchanged."""
        scratch_dir = str(tmp_path / 'scratch')
        large_size = 19373090  # ~19 TB

        free_space = {
            '/': large_size,
            scratch_dir: large_size,
        }

        scratch_dir, mounts_dir, created_images = self._setup_mocks(
            monkeypatch, tmp_path, free_space, None  # unknown limit
        )

        storage_info = make_storage_info(['/'])
        overlaygen._prepare_required_mounts(scratch_dir, mounts_dir, storage_info, scratch_reserve=0)

        # No cap applied - scratch_disk_size = large_size - 0 = large_size
        assert created_images['/'] == large_size
