"""Modular installation on independent copies, with an exact vanilla journal."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from . import legacy_adapter as adapter
from .filesystem import (
    CopyError, COPY_MARKER, atomic_json, checked_path, clone_game, file_sha,
    game_inventory, operation_lock, read_copy_marker, safe_child, update_copy_marker,
    validate_roots,
)
from .processes import require_game_closed
from .profile import resolve_selection


REPO = Path(__file__).resolve().parents[2]
INSTALL_RECORD = '.anno1503-grand-overhaul-install.json'
WORLD_MARKER = '.anno1503-worldsettings-test-copy.json'


class InstallerError(RuntimeError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


def _selection(profile: dict) -> dict:
    profile = resolve_selection(profile, auto_enable_dependencies=True)
    if not (profile['features']['food_overhaul'] or profile['features']['world_settings']):
        raise InstallerError('Select Food overhaul or World Settings. Use Restore original game to remove installed features.')
    return profile


def _workspace() -> Path:
    if getattr(sys, 'frozen', False):
        from .beta_paths import package_workspace
        return package_workspace()
    path = checked_path(REPO / '.local' / 'installer', exists=False)
    path.mkdir(parents=True, exist_ok=True)
    return checked_path(path)


def _read_install(root: Path) -> dict | None:
    path = safe_child(root, INSTALL_RECORD)
    if not path.exists():
        return None
    if path.stat().st_size > 128 * 1024:
        raise InstallerError('The installation record is invalid.')
    value = json.loads(path.read_bytes())
    if (not isinstance(value, dict) or type(value.get('schema')) is not int or value.get('schema') != 1
            or not isinstance(value.get('copy_root'), str) or Path(value.get('copy_root', '')).resolve() != root
            or value.get('baseline') != 'vanilla'
            or value.get('status') not in {'prepared', 'installed', 'restored'}):
        raise InstallerError('The installation record does not match this game copy.')
    return value


def _verify_journal(root: Path, *, installed: bool = True) -> dict:
    record = adapter.read_manifest(root)
    if not record:
        raise InstallerError('No Grand Overhaul restoration backup was found in this copy.')
    if record['source_state'] != 'vanilla':
        raise InstallerError('This backup does not describe an original vanilla game.')
    if installed and record['status'] != 'installed':
        raise InstallerError('The installation is incomplete. Restore this copy before installing again.')
    # Reuse exactly the same whole-file guards used by restoration/preflight.
    tx = adapter._transactions()
    backup = tx._path(root, tx.BACKUP, target=False)
    try:
        for entry in record['edits']:
            allowed = [tx._after(entry)] if installed else [tx._before(entry), tx._after(entry)]
            tx._require(root, entry, allowed)
            if entry['existed']:
                original = tx._path(backup, 'before/' + entry['name'], target=False)
                if tx._state(original) != tx._before(entry):
                    raise InstallerError('A restoration backup is missing or changed: ' + entry['name'])
    except tx.TransactionError as exc:
        raise InstallerError(str(exc)) from exc
    return record


def inspect_copy(copy_game: Path) -> dict:
    root = checked_path(copy_game)
    marker = read_copy_marker(root)
    record = _read_install(root)
    journal = adapter.read_manifest(root)
    return dict(copy_root=str(root), phase=marker['phase'], installation=record,
                transaction_status=None if journal is None else journal['status'])


def check_install(source_game: Path, copy_game: Path, profile: dict,
                  baseline_dir: Path | None = None, package: Path | None = None,
                  progress=lambda _: None) -> dict:
    """Prepare a reviewable plan; writes only to the ignored package workspace."""
    from .packages import prepare_food_package, prepare_package, validate_package
    from .vanilla import plan_vanilla_recovery

    profile = _selection(profile)
    source, target = validate_roots(source_game, copy_game, REPO)
    if target.exists():
        marker = read_copy_marker(target)
        if Path(marker['source_root']).resolve() != source:
            raise InstallerError('This modded copy belongs to a different original game folder.')
        if marker['phase'] in {'copying', 'copied', 'failed'}:
            raise InstallerError('This copy was not fully prepared. Preserve it for inspection and choose a new copy folder.')
        journal = adapter.read_manifest(target)
        if journal and journal['status'] not in {'restored', 'rolled_back'}:
            raise InstallerError('Restore original game in this copy before changing or reinstalling its features.')
    progress('Preparing the selected mod files…')
    if package is None:
        if baseline_dir is None:
            from .beta_paths import package_workspace
            output = package_workspace() / ('package-' + uuid.uuid4().hex)
        else:
            output = _workspace() / ('package-' + uuid.uuid4().hex)
        if profile['features']['world_settings']:
            if baseline_dir is None:
                if profile['features']['food_overhaul']:
                    raise InstallerError('The combined Food + World development build needs its preserved development files. Choose World Settings alone for the public beta, or select the matching files under Advanced. Food is never enabled automatically.')
                from .beta_package import prepare_beta_package
                from .beta_paths import compiler_path
                progress('Building World Settings from your verified game files. This can take a few minutes…')
                package = prepare_beta_package(output, source, target, compiler_path=compiler_path())
            else:
                from .world_options_package import prepare_options_package
                package = prepare_options_package(baseline_dir, output, source, target,
                                                   food_enabled=profile['features']['food_overhaul'])
        else:
            package = prepare_food_package(output, source, copy_game=target)
    package = checked_path(package)
    metadata = validate_package(package, source_game=source)
    if Path(metadata.get('copy_root') or '').resolve() != target:
        raise InstallerError('These prepared mod files belong to another modded copy. Prepare a package for this copy.')
    if profile['features']['world_settings']:
        expected_food = (metadata['food_enabled'] if metadata['kind'] in {'anno1503-world-options-installer-package', 'anno1503-public-beta-world-package'}
                         else metadata['kind'] != 'anno1503-world-only-installer-package')
        if expected_food != profile['features']['food_overhaul']:
            raise InstallerError('The prepared package has a different Food selection. Check the selected features again.')
    food = package / 'food'
    progress('Checking original-game recovery files…')
    recovery = plan_vanilla_recovery(source, food)
    if profile['features']['world_settings'] and profile['features']['food_overhaul']:
        report = adapter.prepare_edits('food', food, source, _workspace() / ('source-check-' + uuid.uuid4().hex), progress)
        if report['state'] != 'combined-0.5.0' or report['edits']:
            raise InstallerError('This preserved combined runtime needs exact Food 0.5 in the Ubisoft source folder. World Settings alone uses its independent stock-game profile.')
        spec = json.loads((package / 'world' / 'world_patch.json').read_bytes())
        expected = {**spec['source_baselines'], **spec['unchanged_native']}
        for name, digest in expected.items():
            if file_sha(safe_child(source, name, exists=True)) != digest:
                raise InstallerError('The World Settings startup module differs from the supported build: ' + name)
    inventory = game_inventory(source) if not target.exists() else []
    return dict(schema=1, source_root=str(source), copy_root=str(target), package_root=str(package),
                package_manifest_sha256=file_sha(package / 'manifest.json'),
                profile=profile, baseline='vanilla', recovery_files=len(recovery),
                copy_files=len(inventory), copy_bytes=sum(item['size'] for item in inventory),
                creates_copy=not target.exists(), checked_at=_now(), game_files_changed=False)


def install(source_game: Path, copy_game: Path, profile: dict, *,
            baseline_dir: Path | None = None, package: Path | None = None,
            progress=lambda _: None) -> dict:
    from .packages import validate_package
    from .vanilla import apply_vanilla_recovery, verify_vanilla

    require_game_closed()
    plan = check_install(source_game, copy_game, profile, baseline_dir, package, progress)
    source, root, package = (Path(plan[key]) for key in ('source_root', 'copy_root', 'package_root'))
    launcher_runtime = None
    if getattr(sys, 'frozen', False) and plan['profile']['features']['world_settings']:
        from .beta_paths import application_data
        from .frozen_runner import application_root, retain_worker
        progress('Keeping a version-matched launcher for this installation…')
        launcher_runtime = retain_worker(application_root(), application_data() / 'Launchers')
    require_game_closed()
    if plan['creates_copy']:
        clone_game(source, root, repo=REPO, progress=progress)
    with operation_lock(root):
        marker = read_copy_marker(root)
        if marker['phase'] == 'copied':
            progress('Preparing the verified original-game baseline in the copy…')
            apply_vanilla_recovery(root, source, package / 'food', progress)
            update_copy_marker(root, phase='vanilla', baseline='vanilla')
        else:
            verify_vanilla(root, package / 'food')
        validate_package(package, source_game=source)
        profile = plan['profile']
        kind = 'world' if profile['features']['world_settings'] else 'food'
        if kind == 'world':
            spec = json.loads((package / 'world' / 'world_patch.json').read_bytes())
            world_marker = dict(schema=1, development_copy=True, source_root=str(source),
                                copy_root=str(root), source_exe_sha256=spec['exe_sha256'])
            marker_path = safe_child(root, WORLD_MARKER)
            if marker_path.exists() and json.loads(marker_path.read_bytes()) != world_marker:
                raise InstallerError('This copy has a conflicting World Settings marker.')
            atomic_json(marker_path, world_marker)
        prepared = adapter.prepare_edits(kind, package / kind, root,
                                         _workspace() / ('prepared-' + uuid.uuid4().hex), progress)
        if prepared['state'] != 'vanilla' or not prepared['edits']:
            raise InstallerError('Installation requires a fully verified original-game baseline.')
        require_game_closed()
        # Revalidate package contents after the isolated preparation, before publication.
        validate_package(package, source_game=source)
        record = dict(schema=1, copy_root=str(root), source_root=str(source), baseline='vanilla',
                      status='prepared', profile=profile, package_root=str(package),
                      package_manifest_sha256=plan['package_manifest_sha256'], prepared_at=_now())
        if launcher_runtime is not None:
            record['launcher_runtime'] = launcher_runtime
        atomic_json(root / INSTALL_RECORD, record)
        journal = adapter.install_prepared(root, prepared, 'vanilla', progress)
        record.update(status='installed', installed_at=_now(), changed_files=len(journal['edits']))
        atomic_json(root / INSTALL_RECORD, record)
        update_copy_marker(root, phase='installed', baseline='vanilla')
        _verify_journal(root)
        return record


def restore(copy_game: Path, *, progress=lambda _: None) -> dict:
    """Restore this installer's vanilla originals; preserve saves and all backups."""
    from .vanilla import verify_vanilla

    require_game_closed()
    root = checked_path(copy_game)
    read_copy_marker(root)
    with operation_lock(root):
        record = _read_install(root)
        if (record and record['profile']['features']['world_settings']
                and not record['profile']['features']['food_overhaul']):
            # World-only leaves these files unowned by the transaction. Check
            # them before removing any World payload, so external changes cannot
            # turn a failed restore into a partially removed installation.
            verify_vanilla(root, REPO / 'legacy' / 'food_overhaul')
        _verify_journal(root, installed=False)
        require_game_closed()
        state = adapter.restore(root, progress)
        if state != 'vanilla':
            raise InstallerError('The restoration journal did not return to the original game.')
        # Restoration uses the pinned source specification; the prepared package
        # is not needed to recover originals from the retained whole-file backup.
        verify_vanilla(root, REPO / 'legacy' / 'food_overhaul')
        update_copy_marker(root, phase='restored', baseline='vanilla')
        if record is not None:
            record.update(status='restored', restored_at=_now())
            atomic_json(root / INSTALL_RECORD, record)
        return dict(restored=True, baseline='vanilla', copy_root=str(root),
                    backups_preserved=True, saves_changed=False)


def launch_world_settings(copy_game: Path):
    """Start the guarded, explicitly bound automatic launcher, without a shell."""
    from .packages import validate_package

    require_game_closed()
    root = checked_path(copy_game)
    marker = read_copy_marker(root)
    record = _read_install(root)
    if not record or record['status'] != 'installed' or not record['profile']['features']['world_settings']:
        raise InstallerError('Install World Settings on this copy before starting its launcher.')
    _verify_journal(root)
    package = checked_path(Path(record['package_root']))
    retained = record.get('launcher_runtime')
    if retained:
        from .frozen_runner import validate_package_closure, verify_retained_worker
        executable = verify_retained_worker(retained)
        validate_package_closure(package, record['package_manifest_sha256'], copy_root=root)
    else:
        validate_package(package, source_game=Path(marker['source_root']))
        executable = Path(sys.executable)
    config = json.loads((package / 'launcher' / 'launcher_config.json').read_bytes())
    if Path(config.get('copy_root', '')).resolve() != root:
        raise InstallerError('The automatic launcher is bound to another game copy.')
    pythonw = executable.with_name('pythonw.exe')
    if pythonw.is_file():
        executable = pythonw
    return subprocess.Popen([str(executable), '-B', str(package / 'launcher' / 'launch_world_settings.pyw')],
                            cwd=package / 'launcher', creationflags=subprocess.CREATE_NO_WINDOW)


def create_world_shortcut(copy_game: Path):
    """Create an entry for the installed version-owned launcher, without starting Anno."""
    from .packages import validate_package
    from .shortcuts import create_desktop_shortcut
    root = checked_path(copy_game)
    marker = read_copy_marker(root)
    record = _read_install(root)
    if not record or record['status'] != 'installed' or not record['profile']['features']['world_settings']:
        raise InstallerError('Install World Settings before creating its shortcut.')
    _verify_journal(root)
    package = checked_path(Path(record['package_root']))
    retained = record.get('launcher_runtime')
    if retained:
        from .frozen_runner import validate_package_closure, verify_retained_worker
        verify_retained_worker(retained)
        validate_package_closure(package, record['package_manifest_sha256'], copy_root=root)
        executable = checked_path(Path(retained['launcher_path']))
    else:
        validate_package(package, source_game=Path(marker['source_root']))
        executable = Path(sys.executable)
        windowless = executable.with_name('pythonw.exe')
        if windowless.is_file():
            executable = windowless
    return create_desktop_shortcut(executable, ['-B', str(package / 'launcher/launch_world_settings.pyw')], package / 'launcher')
