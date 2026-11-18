"""Start the standalone Bug Fixes copy through the verified Ubisoft handoff."""
from __future__ import annotations

from pathlib import Path

from . import installer
from .client_context import start_game
from .filesystem import checked_path, file_sha, read_copy_marker, safe_child
from .food_launch import _make_probes, find_registered_uri, menu_observer_inputs, verified_ubisoft_native
from .packages import BUG_FIXES_PACKAGE_KIND, validate_package
from .processes import require_game_closed
from .vanilla import _spec, verify_vanilla
from .world_runtime_build import STOCK_SHA256


def verify_bug_fixes_installation(copy_game: Path) -> dict:
    root = checked_path(copy_game)
    marker = read_copy_marker(root)
    record = installer._read_install(root)
    if marker['phase'] != 'installed' or installer.installed_launch_kind(record) != 'bug_fixes':
        raise installer.InstallerError('Install the standalone Bug Fixes selection on this copy first.')
    if any(not isinstance(record.get(key), str)
           for key in ('source_root', 'package_root', 'package_manifest_sha256')):
        raise installer.InstallerError('The installed Bug Fixes package binding is incomplete.')
    source = checked_path(Path(marker['source_root']))
    if checked_path(Path(record['source_root'])) != source:
        raise installer.InstallerError('The copy and Bug Fixes installation use different game sources.')
    package = checked_path(Path(record['package_root']))
    if file_sha(safe_child(package, 'manifest.json', exists=True)) != record['package_manifest_sha256']:
        raise installer.InstallerError('The installed Bug Fixes package identity changed.')
    metadata = validate_package(package, source)
    if metadata['kind'] != BUG_FIXES_PACKAGE_KIND or Path(metadata['copy_root']) != root:
        raise installer.InstallerError('The Bug Fixes package belongs to another installation.')
    journal = installer._verify_journal(root)
    quests = metadata['quests']
    expected = {asset['path']: asset for asset in [*quests, *metadata['sounds']]}
    if {entry['name'] for entry in journal['edits']} != expected.keys():
        raise installer.InstallerError('The installed Bug Fixes files differ from their package.')
    for entry in journal['edits']:
        asset = expected[entry['name']]
        if (entry['before_sha256'] != asset['before_sha256']
                or entry['after_sha256'] != asset['after_sha256']):
            raise installer.InstallerError('The installed Bug Fixes file differs from its package: ' + entry['name'])
    for quest in quests:
        if file_sha(safe_child(root, quest['scene_path'], exists=True)) != quest['scene_sha256']:
            raise installer.InstallerError('The installed King of Ore scenario changed: ' + quest['locale'])
    localized_bug_fixes = any(quest['locale'] != 'Nl' for quest in quests)
    if record.get('localized_bug_fixes', False) is not localized_bug_fixes:
        raise installer.InstallerError('The installed Bug Fixes language scope differs from its package.')

    recovery = package / 'food'
    spec = _spec(recovery)
    exe_sha = spec['exe_sha256']
    if file_sha(safe_child(source, 'Anno1503.exe', exists=True)) != exe_sha:
        raise installer.InstallerError('The normal Ubisoft game executable differs from the supported build.')
    recovery_options = {'localized_bug_fixes': True} if localized_bug_fixes else {}
    verify_vanilla(root, recovery, **recovery_options)
    _, source_native = verified_ubisoft_native(source, spec)
    copy_native = {entry['name']: entry['sources']['vanilla'] for entry in spec['native_modules']}
    copy_native['AnnoScene.dll'] = STOCK_SHA256['AnnoScene.dll']
    if file_sha(safe_child(root, 'AnnoScene.dll', exists=True)) != copy_native['AnnoScene.dll']:
        raise installer.InstallerError('The Bug Fixes copy uses an unsupported Scene module.')
    return dict(source_root=source, copy_root=root, package_root=package,
                source_inputs=menu_observer_inputs(source, exe_sha, source_native),
                copy_inputs=menu_observer_inputs(root, exe_sha, copy_native))


def launch_bug_fixes(copy_game: Path, *, progress=None):
    require_game_closed()
    verified = verify_bug_fixes_installation(copy_game)
    source_probe, copy_probe = _make_probes(verified)
    try:
        source = verified['source_root']
        return start_game(find_registered_uri(source), source, verified['copy_root'],
                          source_probe, copy_probe=copy_probe, progress=progress)
    finally:
        source_probe.close()
        copy_probe.close()
