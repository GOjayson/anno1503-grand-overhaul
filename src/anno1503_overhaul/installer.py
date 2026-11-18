"""Modular installation on independent copies, with an exact vanilla journal."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
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
FOOD05_VERSION = '0.5.0'
FOOD06_VERSION = '0.6.0-dev.1'
FOOD06_PACKAGE_KIND = 'anno1503-food06-installer-package'
FOOD_WORLD06_PACKAGE_KIND = 'anno1503-food-world06-installer-package'
PUBLIC_FOOD_WORLD06_PACKAGE_KIND = 'anno1503-public-food-world06-package'
FOOD_WORLD06_PACKAGE_KINDS = {FOOD_WORLD06_PACKAGE_KIND, PUBLIC_FOOD_WORLD06_PACKAGE_KIND}
_MAX_INSTALL_RECORD = 1024 * 1024


class InstallerError(RuntimeError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


def _selection(profile: dict) -> dict:
    profile = resolve_selection(profile, auto_enable_dependencies=True)
    if not any(profile['features'][key] for key in ('food_overhaul', 'world_settings', 'bug_fixes')):
        raise InstallerError('Select a feature to install. Use Restore original game to remove installed features.')
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
    # Six installed language packs can contribute 714 exact Bug Fixes asset
    # fingerprints. Keep that bounded record readable without dropping pins.
    if path.stat().st_size > _MAX_INSTALL_RECORD:
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


def _verify_food06_bug_fixes(root: Path, record: dict, journal: dict | None = None):
    """Reconstruct selected asset fixes; a checkbox or edited journal is no proof.

    This supplements the native Food profile checks. The World launcher also
    verifies its package-bound copy of the same recipe, including direct
    shortcut launches. Older standalone Bug Fixes versions retain their own
    separately versioned package verifier.
    """
    if record.get('food_version') != FOOD06_VERSION:
        return
    features = record.get('profile', {}).get('features', {})
    binding = ('bug_fixes_version', 'bug_fix_quests', 'bug_fix_sounds')
    if features.get('bug_fixes') is not True:
        if any(key in record for key in binding):
            raise InstallerError('The Food installation has Bug Fixes metadata without that feature selected.')
        if journal is None:
            journal = _verify_journal(root)
        from .ambient_sound_baselines import localized_sample_baselines
        from .bug_fixes import KING_OF_ORE_LOCALES, KING_OF_ORE_PATH
        bug_fix_paths = {
            KING_OF_ORE_PATH.replace('/Nl/', '/' + locale + '/').casefold()
            for locale in KING_OF_ORE_LOCALES
        }
        bug_fix_paths.update(
            ('Languages/' + locale + '/Samples/' + name).casefold()
            for locale in KING_OF_ORE_LOCALES
            for name in localized_sample_baselines(locale)
        )
        if any(entry['name'].casefold() in bug_fix_paths for entry in journal.get('edits', ())):
            raise InstallerError('The Food installation owns Bug Fixes assets while that feature is unchecked.')
        return
    if record.get('bug_fixes_version') != '1.2':
        raise InstallerError('The Food installation lacks its reviewed Bug Fixes version binding.')
    if not isinstance(record.get('source_root'), str):
        raise InstallerError('The Food Bug Fixes source binding is incomplete.')
    source = checked_path(Path(record['source_root']))
    marker = read_copy_marker(root)
    if Path(marker['source_root']).resolve() != source:
        raise InstallerError('The Food Bug Fixes and managed copy have different source bindings.')
    from .ambient_sound import ambient_sound_assets
    from .bug_fixes import king_of_ore_assets
    from .packages import ambient_sound_fingerprints, king_of_ore_fingerprints
    quests = king_of_ore_assets(source)
    sounds = ambient_sound_assets(source, (quest.locale for quest in quests))
    if (record.get('bug_fix_quests') != king_of_ore_fingerprints(quests)
            or record.get('bug_fix_sounds') != ambient_sound_fingerprints(sounds)):
        raise InstallerError('The Food Bug Fixes assets differ from their reviewed source recipe.')
    if journal is None:
        journal = _verify_journal(root)
    entries = {entry['name']: entry for entry in journal['edits']}
    for asset, name in [*((quest, quest.quest_path) for quest in quests),
                        *((sound, sound.path) for sound in sounds)]:
        entry = entries.get(name)
        if (entry is None or entry.get('existed') is not True or entry.get('offset') is not None
                or entry.get('before_size') != len(asset.before) or entry.get('after_size') != len(asset.after)
                or entry.get('before_sha256') != hashlib.sha256(asset.before).hexdigest()
                or entry.get('after_sha256') != hashlib.sha256(asset.after).hexdigest()
                or file_sha(safe_child(root, name, exists=True)) != entry['after_sha256']):
            raise InstallerError('The installed Food Bug Fixes asset differs from its recipe: ' + name)
    for quest in quests:
        if file_sha(safe_child(root, quest.scene_path, exists=True)) != quest.scene_sha256:
            raise InstallerError('The installed King of Ore scenario changed: ' + quest.locale)


def inspect_copy(copy_game: Path) -> dict:
    root = checked_path(copy_game)
    marker = read_copy_marker(root)
    record = _read_install(root)
    journal = adapter.read_manifest(root)
    return dict(copy_root=str(root), phase=marker['phase'], installation=record,
                transaction_status=None if journal is None else journal['status'])


def check_install(source_game: Path, copy_game: Path, profile: dict,
                  baseline_dir: Path | None = None, package: Path | None = None,
                  progress=lambda _: None, *, food_version: str | None = None) -> dict:
    """Prepare a reviewable plan; writes only to the ignored package workspace."""
    from .packages import (
        BUG_FIXES_PACKAGE_KIND, ambient_sound_fingerprints, king_of_ore_fingerprints,
        prepare_bug_fixes_package, prepare_food_package, validate_package,
    )
    from .vanilla import plan_vanilla_recovery

    profile = _selection(profile)
    features = profile['features']
    bug_fixes_only = features['bug_fixes'] and not (features['food_overhaul'] or features['world_settings'])
    if food_version not in (None, FOOD05_VERSION, FOOD06_VERSION):
        raise InstallerError('Choose Food 0.6 for new worlds, or the preserved Food 0.5 profile.')
    if food_version is not None and not profile['features']['food_overhaul']:
        raise InstallerError('Select Food overhaul before choosing its version.')
    requested_food_version = (food_version or FOOD05_VERSION) if features['food_overhaul'] else None
    if getattr(sys, 'frozen', False) and requested_food_version == FOOD05_VERSION:
        raise InstallerError('Food 0.5 remains a preserved source development profile. Choose Food 0.6 in this Windows installer.')
    if requested_food_version == FOOD05_VERSION and features['world_settings'] and features['bug_fixes']:
        raise InstallerError('Preserved Food 0.5 + World Settings does not support Bug Fixes. Choose Food 0.6 or leave Food unchecked.')
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
    quests = []
    sounds = []
    if features['bug_fixes']:
        from .bug_fixes import king_of_ore_assets

        quests = king_of_ore_fingerprints(king_of_ore_assets(source))
        if target.exists() and king_of_ore_fingerprints(king_of_ore_assets(target)) != quests:
            raise InstallerError('The copy and source have different King of Ore language files.')
    localized_bug_fixes = bug_fixes_only and any(quest['locale'] != 'Nl' for quest in quests)
    recovery_options = {'localized_bug_fixes': True} if localized_bug_fixes else {}
    progress('Preparing the selected mod files…')
    if package is None:
        if baseline_dir is None:
            from .beta_paths import package_workspace
            output = package_workspace() / ('package-' + uuid.uuid4().hex)
        else:
            output = _workspace() / ('package-' + uuid.uuid4().hex)
        if profile['features']['world_settings']:
            if baseline_dir is not None and getattr(sys, 'frozen', False):
                raise InstallerError('This Windows installer prepares World Settings from your original game. Clear Advanced development files; preserved development profiles use the source installer.')
            if requested_food_version == FOOD06_VERSION:
                progress('Building Food 0.6 with World Settings for a NEW world…')
                combined_options = {'bug_fixes_enabled': True} if features['bug_fixes'] else {}
                if baseline_dir is None:
                    from .food_world_public import prepare_public_food_world_package
                    from .beta_paths import compiler_path
                    package = prepare_public_food_world_package(output, source, target,
                                                                 compiler_path=compiler_path(),
                                                                 **combined_options)
                else:
                    from .food_world_package import prepare_food_world_package
                    package = prepare_food_world_package(baseline_dir, output, source, target,
                                                         **combined_options)
            elif baseline_dir is None:
                if profile['features']['food_overhaul']:
                    raise InstallerError('The combined Food + World development build needs its preserved development files. Choose World Settings alone for the public beta, or select the matching files under Advanced. Food is never enabled automatically.')
                from .beta_package import prepare_beta_package
                from .beta_paths import compiler_path
                progress('Building World Settings from your verified game files. This can take a few minutes…')
                package = prepare_beta_package(output, source, target, compiler_path=compiler_path(),
                                               **({'bug_fixes_enabled': True} if features['bug_fixes'] else {}))
            else:
                from .world_options_package import prepare_options_package
                package = prepare_options_package(baseline_dir, output, source, target,
                                                   food_enabled=profile['features']['food_overhaul'],
                                                   **({'bug_fixes_enabled': True} if features['bug_fixes'] else {}))
        elif requested_food_version == FOOD06_VERSION:
            from .food06_package import prepare_food06_package
            progress('Building Food 0.6 for a NEW Food-only world. Food 0.5 saves are not migrated…')
            package = prepare_food06_package(output, source, copy_game=target)
        elif bug_fixes_only:
            package = prepare_bug_fixes_package(output, source, target)
        else:
            package = prepare_food_package(output, source, copy_game=target)
    package = checked_path(package)
    metadata = validate_package(package, source_game=source)
    if (getattr(sys, 'frozen', False) and features['world_settings']
            and metadata['kind'] not in {'anno1503-public-beta-world-package', PUBLIC_FOOD_WORLD06_PACKAGE_KIND}):
        raise InstallerError('This Windows installer needs a public World Settings recipe. Prepare it without Advanced development files.')
    if (metadata['kind'] == BUG_FIXES_PACKAGE_KIND) != bug_fixes_only:
        raise InstallerError('The prepared package does not match the standalone Bug Fixes selection.')
    if features['bug_fixes']:
        from .ambient_sound import ambient_sound_assets

        locales = tuple(quest['locale'] for quest in quests)
        if bug_fixes_only:
            if metadata['quests'] != quests:
                raise InstallerError('The prepared package has different King of Ore language files. Prepare it again.')
            sounds = metadata['sounds']
        else:
            sounds = ambient_sound_fingerprints(ambient_sound_assets(source, locales))
        if sounds and target.exists() and ambient_sound_fingerprints(ambient_sound_assets(target, locales)) != sounds:
            raise InstallerError('The copy and source have different sound effects.')
    is_combined06 = metadata['kind'] in FOOD_WORLD06_PACKAGE_KINDS
    is_food06 = metadata['kind'] == FOOD06_PACKAGE_KIND or is_combined06
    if metadata['kind'] == FOOD06_PACKAGE_KIND and (features['world_settings'] or not features['food_overhaul']):
        raise InstallerError('This Food 0.6 package is for Food-only installations. It cannot be used by World Settings or the preserved Food 0.5 combined profile.')
    if is_combined06 and not (features['world_settings'] and features['food_overhaul']):
        raise InstallerError('This Food 0.6 + World Settings package requires both features. Prepare the separate Food-only or World-only package for that selection.')
    if features['world_settings']:
        bound_bug_fixes = metadata.get('bug_fixes_enabled', False)
        if type(bound_bug_fixes) is not bool or bound_bug_fixes != features['bug_fixes']:
            raise InstallerError('The prepared World Settings package has a different Bug Fixes selection. Prepare it again for the selected features.')
    actual_food_version = (FOOD06_VERSION if is_food06 else FOOD05_VERSION) if profile['features']['food_overhaul'] else None
    if actual_food_version != requested_food_version:
        raise InstallerError('The prepared package has a different Food version. Prepare the explicitly selected version; Food 0.5 and Food 0.6 are not interchangeable.')
    if Path(metadata.get('copy_root') or '').resolve() != target:
        raise InstallerError('These prepared mod files belong to another modded copy. Prepare a package for this copy.')
    if profile['features']['world_settings']:
        expected_food = (metadata['food_enabled'] if metadata['kind'] in {'anno1503-world-options-installer-package', 'anno1503-public-beta-world-package', *FOOD_WORLD06_PACKAGE_KINDS}
                         else metadata['kind'] != 'anno1503-world-only-installer-package')
        if expected_food != profile['features']['food_overhaul']:
            raise InstallerError('The prepared package has a different Food selection. Check the selected features again.')
    food = package / 'food'
    progress('Checking original-game recovery files…')
    recovery = plan_vanilla_recovery(source, food, **recovery_options)
    if features['world_settings'] and features['food_overhaul'] and not is_combined06:
        report = adapter.prepare_edits('food', food, source, _workspace() / ('source-check-' + uuid.uuid4().hex), progress)
        if report['state'] != 'combined-0.5.0' or report['edits']:
            raise InstallerError('This preserved combined runtime needs exact Food 0.5 in the Ubisoft source folder. World Settings alone uses its independent stock-game profile.')
        spec = json.loads((package / 'world' / 'world_patch.json').read_bytes())
        expected = {**spec['source_baselines'], **spec['unchanged_native']}
        for name, digest in expected.items():
            if file_sha(safe_child(source, name, exists=True)) != digest:
                raise InstallerError('The World Settings startup module differs from the supported build: ' + name)
    inventory = game_inventory(source) if not target.exists() else []
    result = dict(schema=1, source_root=str(source), copy_root=str(target), package_root=str(package),
                package_manifest_sha256=file_sha(package / 'manifest.json'),
                profile=profile, baseline='vanilla', recovery_files=len(recovery),
                copy_files=len(inventory), copy_bytes=sum(item['size'] for item in inventory),
                creates_copy=not target.exists(), checked_at=_now(), game_files_changed=False,
                food_version=actual_food_version)
    if quests:
        result.update(bug_fix_quests=quests, bug_fix_sounds=sounds,
                      bug_fixes_version=(metadata['feature_versions']['bug_fixes'] if bug_fixes_only else '1.2'),
                      localized_bug_fixes=localized_bug_fixes)
    if is_food06:
        result.update(new_world_required=metadata['new_world_required'],
                      old_save_migration_supported=metadata['old_save_migration_supported'],
                      world_settings_supported=metadata['world_settings_supported'])
    return result


def install(source_game: Path, copy_game: Path, profile: dict, *,
            baseline_dir: Path | None = None, package: Path | None = None,
            progress=lambda _: None, food_version: str | None = None) -> dict:
    from .packages import ambient_sound_fingerprints, king_of_ore_fingerprints, validate_package
    from .vanilla import apply_vanilla_recovery, verify_vanilla

    require_game_closed()
    plan = check_install(source_game, copy_game, profile, baseline_dir, package, progress,
                         food_version=food_version)
    source, root, package = (Path(plan[key]) for key in ('source_root', 'copy_root', 'package_root'))
    launcher_runtime = None
    if (getattr(sys, 'frozen', False) and (plan['profile']['features']['world_settings']
                                         or plan.get('food_version') == FOOD06_VERSION)):
        from .beta_paths import application_data
        from .frozen_runner import application_root, retain_worker
        progress('Keeping a version-matched launcher for this installation…')
        launcher_runtime = retain_worker(application_root(), application_data() / 'Launchers')
    require_game_closed()
    if plan['creates_copy']:
        clone_game(source, root, repo=REPO, progress=progress)
    recovery_options = {'localized_bug_fixes': True} if plan.get('localized_bug_fixes') else {}
    with operation_lock(root):
        marker = read_copy_marker(root)
        if marker['phase'] == 'copied':
            progress('Preparing the verified original-game baseline in the copy…')
            apply_vanilla_recovery(root, source, package / 'food', progress, **recovery_options)
            update_copy_marker(root, phase='vanilla', baseline='vanilla')
        else:
            verify_vanilla(root, package / 'food', **recovery_options)
        validate_package(package, source_game=source)
        profile = plan['profile']
        features = profile['features']
        kind = 'world' if features['world_settings'] else 'food' if features['food_overhaul'] else None
        bug_fix_edits = ()
        if features['bug_fixes']:
            from .ambient_sound import ambient_sound_assets
            from .bug_fixes import king_of_ore_assets

            quests = king_of_ore_assets(root)
            if king_of_ore_fingerprints(quests) != plan['bug_fix_quests']:
                raise InstallerError('The copy and checked source have different King of Ore language files.')
            sounds = ()
            if plan['bug_fix_sounds']:
                sounds = ambient_sound_assets(root, (quest.locale for quest in quests))
                if ambient_sound_fingerprints(sounds) != plan['bug_fix_sounds']:
                    raise InstallerError('The copy and checked source have different sound effects.')
            edit = adapter._transactions().Edit
            bug_fix_edits = (
                *(edit(quest.quest_path, quest.before, quest.after, len(quest.before)) for quest in quests),
                *(edit(sound.path, sound.before, sound.after, len(sound.before)) for sound in sounds),
            )
        if kind == 'world':
            spec = json.loads((package / 'world' / 'world_patch.json').read_bytes())
            world_marker = dict(schema=1, development_copy=True, source_root=str(source),
                                copy_root=str(root), source_exe_sha256=spec['exe_sha256'])
            marker_path = safe_child(root, WORLD_MARKER)
            if marker_path.exists() and json.loads(marker_path.read_bytes()) != world_marker:
                raise InstallerError('This copy has a conflicting World Settings marker.')
            atomic_json(marker_path, world_marker)
        prepared = None
        if kind is not None:
            prepared = adapter.prepare_edits(kind, package / kind, root,
                                             _workspace() / ('prepared-' + uuid.uuid4().hex), progress)
            if prepared['state'] != 'vanilla' or not prepared['edits']:
                raise InstallerError('Installation requires a fully verified original-game baseline.')
            prepared_names = {entry['name'].casefold() for entry in prepared['edits']}
            for bug_fix in bug_fix_edits:
                if bug_fix.name.casefold() in prepared_names:
                    raise InstallerError('Selected features modify the same game file: ' + bug_fix.name)
        require_game_closed()
        # Revalidate package contents after the isolated preparation, before publication.
        validate_package(package, source_game=source)
        if file_sha(package / 'manifest.json') != plan['package_manifest_sha256']:
            raise InstallerError('The prepared package changed after Check installation.')
        record = dict(schema=1, copy_root=str(root), source_root=str(source), baseline='vanilla',
                      status='prepared', profile=profile, package_root=str(package),
                      package_manifest_sha256=plan['package_manifest_sha256'], prepared_at=_now())
        if plan.get('food_version') is not None:
            record['food_version'] = plan['food_version']
        if features['bug_fixes']:
            record.update(bug_fixes_version=plan['bug_fixes_version'], bug_fix_quests=plan['bug_fix_quests'],
                          bug_fix_sounds=plan['bug_fix_sounds'])
        record.update(recovery_options)
        if plan.get('new_world_required'):
            record.update(new_world_required=True,
                          old_save_migration_supported=plan['old_save_migration_supported'],
                          world_settings_supported=plan['world_settings_supported'])
        if launcher_runtime is not None:
            record['launcher_runtime'] = launcher_runtime
        atomic_json(root / INSTALL_RECORD, record)
        additional = {'additional_edits': bug_fix_edits} if bug_fix_edits else {}
        journal = adapter.install_prepared(root, prepared, 'vanilla', progress, **additional)
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
        recovery_options = {}
        if record and record.get('localized_bug_fixes') is True:
            features = record['profile']['features']
            if not features.get('bug_fixes') or features['food_overhaul'] or features['world_settings']:
                raise InstallerError('The localized Bug Fixes backup has an incompatible selection.')
            recovery_options['localized_bug_fixes'] = True
        if record and not record['profile']['features']['food_overhaul']:
            # Selections without Food leave these files unowned by the transaction.
            # Check them before restoring anything.
            verify_vanilla(root, REPO / 'legacy' / 'food_overhaul', **recovery_options)
        _verify_journal(root, installed=False)
        require_game_closed()
        state = adapter.restore(root, progress)
        if state != 'vanilla':
            raise InstallerError('The restoration journal did not return to the original game.')
        # Restoration uses the pinned source specification; the prepared package
        # is not needed to recover originals from the retained whole-file backup.
        verify_vanilla(root, REPO / 'legacy' / 'food_overhaul', **recovery_options)
        update_copy_marker(root, phase='restored', baseline='vanilla')
        if record is not None:
            record.update(status='restored', restored_at=_now())
            atomic_json(root / INSTALL_RECORD, record)
        return dict(restored=True, baseline='vanilla', copy_root=str(root),
                    backups_preserved=True, saves_changed=False)


def installed_launch_kind(record: dict | None) -> str | None:
    """Describe a supported installed route, independently of current checkboxes."""
    if not isinstance(record, dict) or record.get('status') != 'installed':
        return None
    selected = record.get('profile')
    if not isinstance(selected, dict) or not isinstance(selected.get('features'), dict):
        return None
    features = selected['features']
    if features.get('world_settings') is True:
        if record.get('food_version') == FOOD06_VERSION:
            return 'food06-world' if features.get('food_overhaul') is True else None
        return 'world'
    if (features.get('world_settings') is False and features.get('food_overhaul') is True
            and record.get('food_version') == FOOD06_VERSION):
        return 'food06'
    if (features.get('bug_fixes') is True and features.get('food_overhaul') is False
            and features.get('world_settings') is False):
        return 'bug_fixes'
    return None


def launch_installed_game(copy_game: Path, *, progress=None):
    """Dispatch only the exact installed copy's supported startup route."""
    root = checked_path(copy_game)
    marker = read_copy_marker(root)
    record = _read_install(root)
    route = installed_launch_kind(record)
    if marker['phase'] != 'installed' or route is None:
        selected = record.get('profile') if isinstance(record, dict) else None
        features = selected.get('features') if isinstance(selected, dict) else None
        if (route is None and record and record.get('status') == 'installed'
                and isinstance(features, dict) and features.get('food_overhaul') is True
                and record.get('food_version') in (None, FOOD05_VERSION)):
            raise InstallerError('Automatic Food 0.5 startup is not available here. Use your existing known-working Food 0.5 game or shortcut and its preserved startup instructions. This button supports World Settings or Food 0.6.')
        raise InstallerError('Install Bug Fixes, World Settings or the explicit Food 0.6 profile before starting this copy.')
    journal = _verify_journal(root)
    _verify_food06_bug_fixes(root, record, journal)
    if route in ('world', 'food06-world'):
        return launch_world_settings(root)
    if route == 'bug_fixes':
        from .bug_fixes_launch import launch_bug_fixes
        return launch_bug_fixes(root, progress=progress)
    if record.get('launcher_runtime') is not None or getattr(sys, 'frozen', False):
        return launch_retained_food06(root)
    from .food_launch import launch_food06
    return launch_food06(root, progress=progress)


def launch_retained_food06(copy_game: Path):
    """Start Food-only through its sealed, version-owned Windows launcher."""
    from .frozen_runner import validate_package_closure, verify_retained_worker
    require_game_closed()
    root = checked_path(copy_game)
    marker = read_copy_marker(root)
    record = _read_install(root)
    if marker['phase'] != 'installed' or installed_launch_kind(record) != 'food06':
        raise InstallerError('Install the Food 0.6 Food-only profile before starting its retained launcher.')
    journal = _verify_journal(root)
    _verify_food06_bug_fixes(root, record, journal)
    retained = record.get('launcher_runtime')
    if not isinstance(retained, dict) or not isinstance(retained.get('launcher_path'), str):
        raise InstallerError('This Food installation has no retained Windows launcher. Restore and reinstall it with the current installer.')
    worker = verify_retained_worker(retained)
    package = checked_path(Path(record['package_root']))
    metadata = validate_package_closure(package, record['package_manifest_sha256'], copy_root=root)
    if metadata.get('kind') != FOOD06_PACKAGE_KIND:
        raise InstallerError('The retained Food launcher requires its exact Food-only package.')
    executable = checked_path(Path(retained['launcher_path']))
    return subprocess.Popen([str(executable), '--launch-food06', '--copy', str(root)],
                            cwd=worker.parent, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def launch_world_settings(copy_game: Path):
    """Start the guarded, explicitly bound automatic launcher, without a shell."""
    from .packages import validate_package

    require_game_closed()
    root = checked_path(copy_game)
    marker = read_copy_marker(root)
    record = _read_install(root)
    if not record or record['status'] != 'installed' or not record['profile']['features']['world_settings']:
        raise InstallerError('Install World Settings on this copy before starting its launcher.')
    journal = _verify_journal(root)
    _verify_food06_bug_fixes(root, record, journal)
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
    journal = _verify_journal(root)
    _verify_food06_bug_fixes(root, record, journal)
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
