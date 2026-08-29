from __future__ import annotations

import json
import os
import sqlite3
import stat
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import infrastructure.workspace.package as package_module

from infrastructure.workspace import (
    Argon2Parameters,
    InvalidWorkspacePackage,
    PackageLimits,
    WorkspaceAuthenticationError,
    WorkspaceConflictError,
    WorkspaceLimitExceeded,
    WorkspacePackageCodec,
    WorkspacePasswordRequired,
    WorkspaceService,
)


class WorkspacePackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.codec = WorkspacePackageCodec(
            app_version="9.8.7-test",
            encryption_parameters=Argon2Parameters(
                memory_cost_kib=8 * 1024, iterations=1, lanes=1
            ),
        )
        self.workspace = self.root / "source"
        self._make_workspace(self.workspace)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _make_workspace(root: Path) -> None:
        root.mkdir(parents=True)
        for name, marker in (
            ("device_network.db", "device"),
            ("info_collected.db", "collected"),
        ):
            with closing(sqlite3.connect(root / name)) as database:
                database.execute("CREATE TABLE marker (value TEXT NOT NULL)")
                database.execute("INSERT INTO marker VALUES (?)", (marker,))
                database.execute("PRAGMA user_version = 3")
                database.commit()
        backup = root / "backup" / "router-01"
        backup.mkdir(parents=True)
        (backup / "running-config.txt").write_bytes(b"hostname router-01\n")
        (root / "backup" / "reserved-empty-folder").mkdir()
        snapshots = root / "snapshots"
        snapshots.mkdir()
        (snapshots / "index.json").write_text(
            json.dumps({"formatVersion": 1, "snapshots": []}) + "\n",
            encoding="utf-8",
        )

    def test_plaintext_round_trip_is_an_ordinary_zip_and_uses_temp_workspace(self) -> None:
        package = self.root / "Campus.ntp"
        manifest = self.codec.pack(
            self.workspace, package, project_name="Campus Network"
        )

        self.assertTrue(zipfile.is_zipfile(package))
        self.assertFalse(self.codec.is_encrypted(package))
        with zipfile.ZipFile(package) as archive:
            self.assertEqual(archive.infolist()[0].filename, "manifest.json")
            self.assertIn("backup/", archive.namelist())
            self.assertIn("snapshots/index.json", archive.namelist())
        self.assertEqual(manifest.name, "Campus Network")
        self.assertEqual(manifest.database_schema_versions["deviceNetwork"], 3)

        session = self.codec.open(package)
        working_directory = session.working_directory
        self.assertNotEqual(working_directory, self.workspace)
        self.assertTrue(working_directory.is_dir())
        self.assertEqual(
            (working_directory / "backup/router-01/running-config.txt").read_bytes(),
            b"hostname router-01\n",
        )
        self.assertTrue(
            (working_directory / "backup/reserved-empty-folder").is_dir()
        )
        session.close()
        self.assertFalse(working_directory.exists())

    def test_project_cannot_be_opened_by_overlapping_sessions(self) -> None:
        package = self.root / "Exclusive.ntp"
        self.codec.pack(self.workspace, package, project_name="Exclusive")

        first = self.codec.open(package)
        try:
            with self.assertRaisesRegex(
                WorkspaceConflictError, "already open in another NetworkTools session"
            ):
                self.codec.open(package)
        finally:
            first.close()

        reopened = self.codec.open(package)
        reopened.close()

    def test_failed_open_releases_project_lease(self) -> None:
        package = self.root / "BrokenLease.ntp"
        package.write_bytes(b"not a workspace")

        with self.assertRaises(InvalidWorkspacePackage):
            self.codec.open(package)
        with self.assertRaises(InvalidWorkspacePackage):
            self.codec.open(package)

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links unavailable")
    def test_project_lock_sidecar_cannot_redirect_metadata_through_symlink(self) -> None:
        package = self.root / "SafeLock.ntp"
        self.codec.pack(self.workspace, package)
        protected = self.root / "protected.txt"
        protected.write_text("keep me", encoding="utf-8")
        sidecar = package.with_name(f".{package.name}.workspace.lock")
        try:
            sidecar.symlink_to(protected)
        except OSError as exc:
            self.skipTest(f"symbolic links unavailable: {exc}")

        with self.assertRaises(WorkspaceConflictError):
            self.codec.open(package)

        self.assertEqual(protected.read_text(encoding="utf-8"), "keep me")

    def test_manifest_uses_compact_json_for_large_content_inventories(self) -> None:
        entries = tuple(
            package_module.ContentEntry(
                path=(
                    "snapshots/00000000-0000-0000-0000-000000000000/backup/"
                    f"router/cfg/.networktools-git/objects/{index:04x}/"
                    "0123456789abcdef0123456789abcdef01234567"
                ),
                size=index,
                sha256="0" * 64,
            )
            for index in range(4_000)
        )
        manifest = package_module.WorkspaceManifest(
            project_id="00000000-0000-0000-0000-000000000001",
            name="Large inventory",
            created_at="2026-08-23T00:00:00Z",
            modified_at="2026-08-23T00:00:00Z",
            created_by_app_version="test",
            last_saved_by_app_version="test",
            minimum_reader_version="0.1.0",
            database_schema_versions={"deviceNetwork": 1, "infoCollected": 1},
            content=entries,
        )

        payload = manifest.to_bytes()

        self.assertNotIn(b'\n  "content"', payload)
        self.assertLess(len(payload), 1024 * 1024)
        self.assertEqual(
            package_module.WorkspaceManifest.from_bytes(payload).content,
            entries,
        )
        self.assertIsNone(PackageLimits().max_manifest_size)
        self.assertIsNone(PackageLimits().max_members)
        self.assertIsNone(PackageLimits().max_entry_size)
        self.assertIsNone(PackageLimits().max_total_size)
        self.assertIsNone(PackageLimits().max_package_size)

    def test_custom_manifest_size_limit_is_still_enforced(self) -> None:
        package = self.root / "ManifestLimited.ntp"
        self.codec.pack(self.workspace, package)
        strict_codec = WorkspacePackageCodec(
            limits=PackageLimits(max_manifest_size=64)
        )

        with self.assertRaises(WorkspaceLimitExceeded):
            strict_codec.open(package)

    def test_session_cleanup_can_retry_after_a_windows_sharing_failure(self) -> None:
        session = self.codec.new_session(self.root / "Retry.ntp", "Retry")
        working_directory = session.working_directory
        real_cleanup = session._temporary_directory.cleanup
        attempts = 0

        def flaky_cleanup():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise PermissionError("simulated open handle")
            real_cleanup()

        with patch.object(
            session._temporary_directory, "cleanup", side_effect=flaky_cleanup
        ):
            with self.assertRaises(PermissionError):
                session.close()
            self.assertTrue(working_directory.exists())
            session.close()

        self.assertEqual(attempts, 2)
        self.assertFalse(working_directory.exists())

    def test_encrypted_round_trip_requires_password_and_hides_zip_metadata(self) -> None:
        package = self.root / "Protected.ntp"
        self.codec.pack(
            self.workspace,
            package,
            password="correct horse battery staple",
            project_name="Protected Lab",
        )

        self.assertFalse(zipfile.is_zipfile(package))
        self.assertTrue(self.codec.is_encrypted(package))
        self.assertNotIn(b"device_network.db", package.read_bytes())
        with self.assertRaises(WorkspacePasswordRequired):
            self.codec.open(package)
        with self.assertRaises(WorkspaceAuthenticationError):
            self.codec.open(package, "wrong password")

        with self.codec.open(package, "correct horse battery staple") as session:
            self.assertTrue(session.encrypted)
            self.assertEqual(session.manifest.name, "Protected Lab")
            with self.assertRaises(WorkspaceConflictError):
                self.codec.open(package)
            with closing(sqlite3.connect(session.device_network_db)) as database:
                self.assertEqual(
                    database.execute("SELECT value FROM marker").fetchone(),
                    ("device",),
                )

    def test_ciphertext_or_tag_tampering_is_authenticated(self) -> None:
        package = self.root / "Tampered.ntp"
        self.codec.pack(self.workspace, package, password="secret passphrase")
        damaged = bytearray(package.read_bytes())
        damaged[-1] ^= 0x80
        package.write_bytes(damaged)

        with self.assertRaises(WorkspaceAuthenticationError):
            self.codec.open(package, "secret passphrase")

    def test_wrong_password_and_corruption_remove_decryption_workspace(self) -> None:
        package = self.root / "Private.ntp"
        self.codec.pack(self.workspace, package, password="right password")
        created_workspaces: list[Path] = []
        original_factory = self.codec._make_temporary_workspace

        def recording_factory():
            temporary, working = original_factory()
            created_workspaces.append(working)
            return temporary, working

        with patch.object(
            self.codec, "_make_temporary_workspace", side_effect=recording_factory
        ):
            with self.assertRaises(WorkspaceAuthenticationError) as wrong:
                self.codec.open(package, "wrong password")
            damaged = bytearray(package.read_bytes())
            damaged[-1] ^= 0x01
            package.write_bytes(damaged)
            with self.assertRaises(WorkspaceAuthenticationError) as corrupt:
                self.codec.open(package, "right password")

        self.assertEqual(str(wrong.exception), str(corrupt.exception))
        self.assertTrue(created_workspaces)
        self.assertTrue(all(not path.exists() for path in created_workspaces))

    def test_repack_preserves_project_identity_and_replaces_via_tmp(self) -> None:
        package = self.root / "Repacked.ntp"
        original = self.codec.pack(self.workspace, package, project_name="Original")
        (self.workspace / "backup/router-01/running-config.txt").write_bytes(b"changed\n")
        updated = self.codec.pack(
            self.workspace,
            package,
            project_name="Updated",
            base_manifest=original,
        )

        self.assertEqual(updated.project_id, original.project_id)
        self.assertEqual(updated.created_at, original.created_at)
        self.assertEqual(updated.name, "Updated")
        self.assertFalse((self.root / "Repacked.ntp.tmp").exists())
        with self.codec.open(package) as session:
            self.assertEqual(
                (session.backup_directory / "router-01/running-config.txt").read_bytes(),
                b"changed\n",
            )

    def test_failed_pack_does_not_replace_last_valid_project(self) -> None:
        package = self.root / "Stable.ntp"
        self.codec.pack(self.workspace, package)
        original_bytes = package.read_bytes()
        (self.workspace / "unexpected.cache").write_bytes(b"not package content")

        with self.assertRaises(InvalidWorkspacePackage):
            self.codec.pack(self.workspace, package)

        self.assertEqual(package.read_bytes(), original_bytes)
        self.assertFalse((self.root / "Stable.ntp.tmp").exists())

    def test_failed_pack_does_not_mutate_live_manifest(self) -> None:
        package = self.root / "ManifestStable.ntp"
        original = self.codec.pack(self.workspace, package)
        manifest_path = self.workspace / "manifest.json"
        manifest_path.write_bytes(original.to_bytes())
        original_manifest = manifest_path.read_bytes()
        (self.workspace / "unexpected.cache").write_bytes(b"reject this save")

        with self.assertRaises(InvalidWorkspacePackage):
            self.codec.pack(
                self.workspace, package, project_name="Must not leak", base_manifest=original
            )

        self.assertEqual(manifest_path.read_bytes(), original_manifest)

    def test_crash_fragment_is_quarantined_and_does_not_block_next_save(self) -> None:
        package = self.root / "Recoverable.ntp"
        self.codec.pack(self.workspace, package)
        sidecar = package.with_name(package.name + ".tmp")
        sidecar.write_bytes(b"PK\x03\x04truncated-by-crash")

        self.codec.pack(self.workspace, package)

        self.assertFalse(sidecar.exists())
        quarantined = list(self.root.glob("Recoverable.ntp.tmp.corrupt-*"))
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(quarantined[0].read_bytes(), b"PK\x03\x04truncated-by-crash")
        self.assertTrue(zipfile.is_zipfile(package))

    def test_verified_recovery_sidecar_is_never_overwritten(self) -> None:
        package = self.root / "RecoveryCandidate.ntp"
        self.codec.pack(self.workspace, package)
        sidecar = package.with_name(package.name + ".tmp")
        sidecar.write_bytes(package.read_bytes())
        recovery_bytes = sidecar.read_bytes()

        with self.assertRaises(WorkspaceConflictError):
            self.codec.pack(self.workspace, package)

        self.assertEqual(sidecar.read_bytes(), recovery_bytes)

    def test_replace_failure_preserves_verified_sidecar_and_original(self) -> None:
        package = self.root / "Locked.ntp"
        self.codec.pack(self.workspace, package)
        original_bytes = package.read_bytes()
        sidecar = package.with_name(package.name + ".tmp")
        original_replace = package_module.os.replace

        def deny_final_replace(source, destination):
            if Path(source) == sidecar and Path(destination) == package:
                raise PermissionError("destination is locked")
            return original_replace(source, destination)

        with patch.object(package_module.os, "replace", side_effect=deny_final_replace):
            with self.assertRaises(PermissionError):
                self.codec.pack(self.workspace, package)

        self.assertEqual(package.read_bytes(), original_bytes)
        self.assertTrue(zipfile.is_zipfile(sidecar))

    def test_traversal_member_is_rejected_before_extraction(self) -> None:
        package = self.root / "Traversal.ntp"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("manifest.json", b"{}")
            archive.writestr("../escaped.txt", b"escaped")

        with self.assertRaises(InvalidWorkspacePackage):
            self.codec.open(package)
        self.assertFalse((self.root / "escaped.txt").exists())

    def test_case_colliding_members_are_rejected(self) -> None:
        package = self.root / "Collision.ntp"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("manifest.json", b"{}")
            archive.writestr("backup/", b"")
            archive.writestr("backup/Router.txt", b"one")
            archive.writestr("backup/router.txt", b"two")

        with self.assertRaises(InvalidWorkspacePackage):
            self.codec.open(package)

    def test_file_directory_tree_conflict_is_rejected_before_extraction(self) -> None:
        package = self.root / "TreeConflict.ntp"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("manifest.json", b"{}")
            archive.writestr("backup/", b"")
            archive.writestr("backup/router", b"not a directory")
            archive.writestr("backup/router/running-config.txt", b"hostname R1\n")

        with self.assertRaisesRegex(
            InvalidWorkspacePackage, "nested below a file"
        ):
            self.codec.open(package)

    def test_file_cannot_replace_an_existing_archive_directory_tree(self) -> None:
        package = self.root / "ReverseTreeConflict.ntp"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("manifest.json", b"{}")
            archive.writestr("backup/", b"")
            archive.writestr("backup/router/running-config.txt", b"hostname R1\n")
            archive.writestr("backup/router", b"not a directory")

        with self.assertRaisesRegex(
            InvalidWorkspacePackage, "conflicts with a directory tree"
        ):
            self.codec.open(package)

    def test_case_colliding_implicit_directories_are_rejected(self) -> None:
        package = self.root / "DirectoryCaseConflict.ntp"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("manifest.json", b"{}")
            archive.writestr("backup/", b"")
            archive.writestr("backup/Router/one.txt", b"one")
            archive.writestr("backup/router/two.txt", b"two")

        with self.assertRaisesRegex(
            InvalidWorkspacePackage, "Case-colliding archive path component"
        ):
            self.codec.open(package)

    def test_symlink_member_is_rejected(self) -> None:
        package = self.root / "Symlink.ntp"
        link = zipfile.ZipInfo("backup/link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("manifest.json", b"{}")
            archive.writestr(link, b"../../outside")

        with self.assertRaises(InvalidWorkspacePackage):
            self.codec.open(package)

    def test_manifest_checksum_mismatch_is_rejected(self) -> None:
        package = self.root / "Checksum.ntp"
        self.codec.pack(self.workspace, package)
        rewritten = self.root / "rewritten.zip"
        with zipfile.ZipFile(package, "r") as source, zipfile.ZipFile(
            rewritten, "w"
        ) as destination:
            for member in source.infolist():
                payload = source.read(member)
                if member.filename == "backup/router-01/running-config.txt":
                    payload = b"hostname attacker\n"
                destination.writestr(member, payload)
        os.replace(rewritten, package)

        with self.assertRaises(InvalidWorkspacePackage):
            self.codec.open(package)

    def test_malformed_plaintext_package_uses_typed_error(self) -> None:
        package = self.root / "Broken.ntp"
        package.write_bytes(b"PK\x03\x04truncated")

        with self.assertRaises(InvalidWorkspacePackage):
            self.codec.open(package)

    def test_package_destination_cannot_be_inside_working_directory(self) -> None:
        with self.assertRaises(ValueError):
            self.codec.pack(self.workspace, self.workspace / "Recursive.ntp")

    def test_declared_expansion_limit_is_enforced(self) -> None:
        package = self.root / "Limited.ntp"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("manifest.json", b"{}")
            archive.writestr("backup/large.bin", b"x" * 256)
        strict_codec = WorkspacePackageCodec(
            limits=PackageLimits(max_total_size=128)
        )

        with self.assertRaises(WorkspaceLimitExceeded):
            strict_codec.open(package)

    def test_oversized_package_is_rejected_before_temp_workspace_allocation(self) -> None:
        package = self.root / "Oversized.ntp"
        package.write_bytes(b"PK" + b"x" * 256)
        strict_codec = WorkspacePackageCodec(
            limits=PackageLimits(max_package_size=128)
        )

        with patch.object(strict_codec, "_make_temporary_workspace") as factory:
            with self.assertRaises(WorkspaceLimitExceeded):
                strict_codec.open(package)

        factory.assert_not_called()


class WorkspaceServiceTests(unittest.TestCase):
    def test_create_project_builds_both_databases_and_first_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "New Project.ntp"
            service = WorkspaceService()
            session = service.create_project("New Project", target)
            try:
                self.assertTrue(target.is_file())
                self.assertTrue(zipfile.is_zipfile(target))
                self.assertTrue(session.device_network_db.is_file())
                self.assertTrue(session.info_collected_db.is_file())
                self.assertTrue(session.backup_directory.is_dir())
            finally:
                session.close()

    def test_create_project_never_overwrites_an_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "Existing.ntp"
            target.write_bytes(b"keep me")

            with self.assertRaises(FileExistsError):
                WorkspaceService().create_project("Existing", target)

            self.assertEqual(target.read_bytes(), b"keep me")

    def test_repack_never_silently_removes_existing_password_protection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "Protected.ntp"
            codec = WorkspacePackageCodec(
                encryption_parameters=Argon2Parameters(
                    memory_cost_kib=8 * 1024, iterations=1, lanes=1
                )
            )
            service = WorkspaceService(codec)
            session = service.create_project(
                "Protected", target, password="active password"
            )
            try:
                service.pack_project(session)
                self.assertTrue(service.is_encrypted(target))

                service.pack_project(session, password="active password")
                self.assertTrue(service.is_encrypted(target))
            finally:
                session.close()

    def test_save_as_transfers_ownership_to_the_new_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "Source.ntp"
            destination = Path(temp) / "Destination.ntp"
            service = WorkspaceService()
            session = service.create_project("Source", source)
            try:
                service.pack_project(session, package_path=destination)
                self.assertEqual(session.project_path, destination)

                source_session = service.open_project(source)
                source_session.close()
                with self.assertRaises(WorkspaceConflictError):
                    service.open_project(destination)
            finally:
                session.close()

            destination_session = service.open_project(destination)
            destination_session.close()


if __name__ == "__main__":
    unittest.main()
