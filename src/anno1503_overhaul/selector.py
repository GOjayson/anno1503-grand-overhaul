"""Installer interface. World-specific choices stay inside Anno."""
from pathlib import Path
import os
import queue
import threading

from .features import default_catalog
from .profile import load_profile, save_profile, resolve_selection


def _registered_game():
    if os.name != 'nt':
        return ''
    import winreg
    matches = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Ubisoft\Launcher\Installs',
                            0, winreg.KEY_READ | winreg.KEY_WOW64_32KEY) as installs:
            for index in range(winreg.QueryInfoKey(installs)[0]):
                with winreg.OpenKey(installs, winreg.EnumKey(installs, index)) as item:
                    try:
                        folder = Path(winreg.QueryValueEx(item, 'InstallDir')[0])
                        if (folder / 'Anno1503.exe').is_file():
                            matches.append(folder)
                    except OSError:
                        pass
    except OSError:
        pass
    return str(matches[0]) if len(matches) == 1 else ''


def main():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    from . import installer

    root = tk.Tk()
    root.title('Anno 1503 Grand Overhaul — Installer')
    root.geometry('900x790')
    root.minsize(820, 740)
    panel = ttk.Frame(root, padding=22)
    panel.pack(fill='both', expand=True)
    ttk.Label(panel, text='Anno 1503 Grand Overhaul', font=('Segoe UI', 19, 'bold')).pack(anchor='w')
    ttk.Label(panel, text='Install selected features on a separate game copy. Choose world options inside Anno.',
              wraplength=840).pack(anchor='w', pady=(6, 16))
    catalog = default_catalog()
    source = tk.StringVar(value=_registered_game())
    target = tk.StringVar(value=str(installer.REPO / '.local/game-copies/Grand Overhaul'))
    provider = tk.StringVar(value=str(installer.REPO / '.local/baselines'))
    name = tk.StringVar(value='Default')
    flags = {f.id: tk.BooleanVar(value=f.default_enabled) for f in catalog.features}
    mutable, controls, buttons = [], {}, {}
    status = tk.StringVar(value='Choose features, then check the installation.')
    busy, checked = [False], [None]
    events = queue.Queue()

    def choose_folder(var, title):
        selected = filedialog.askdirectory(parent=root, title=title, mustexist=False, initialdir=var.get() or None)
        if selected:
            var.set(selected)

    for label, variable, title in (
        ('Original game folder', source, 'Select the installed Anno 1503 History Edition folder'),
        ('Modded copy folder', target, 'Choose a separate folder for the modded game copy'),
        ('World Settings files', provider, 'Select the baseline store containing food_overhaul, world_settings and launcher'),
    ):
        row = ttk.Frame(panel)
        row.pack(fill='x', pady=4)
        ttk.Label(row, text=label, width=22).pack(side='left')
        entry = ttk.Entry(row, textvariable=variable)
        entry.pack(side='left', fill='x', expand=True, padx=(0, 8))
        button = ttk.Button(row, text='Browse…', command=lambda v=variable, t=title: choose_folder(v, t))
        button.pack(side='right')
        mutable.extend((entry, button))
    ttk.Label(panel, text='Your original folder, existing backups and saves are preserved. Restore affects the modded copy.',
              foreground='#555555', wraplength=840).pack(anchor='w', pady=(7, 12))
    group = ttk.LabelFrame(panel, text='Features', padding=12)
    group.pack(fill='x')

    def selection():
        return dict(schema_version=1, name=name.get(), features={k: v.get() for k, v in flags.items()})

    def update_buttons():
        can_start = False
        if not busy[0]:
            try:
                info = installer.inspect_copy(Path(target.get()))
                record = info['installation']
                can_start = bool(record and record['status'] == 'installed'
                                 and record['profile']['features']['world_settings'])
            except Exception:
                pass
        for key, button in buttons.items():
            disabled = busy[0] or (key == 'install' and checked[0] is None) or (key == 'start' and not can_start)
            button.state(['disabled'] if disabled else ['!disabled'])

    def refresh(*_):
        checked[0] = None
        if flags['world_settings'].get():
            flags['food_overhaul'].set(True)
        if 'food_overhaul' in controls:
            controls['food_overhaul'].state(['disabled'] if flags['world_settings'].get() or busy[0] else ['!disabled'])
        if not busy[0]:
            status.set('World Settings requires Food in this release.' if flags['world_settings'].get()
                       else 'Choose features, then check the installation.')
            update_buttons()

    for key, description in (
        ('world_settings', 'World size, preview, islands, fertility, starting options and opponents — inside Anno.'),
        ('food_overhaul', 'Food 0.5 and its existing gameplay changes.'),
    ):
        check = ttk.Checkbutton(group, text=catalog[key].name, variable=flags[key], command=refresh)
        check.pack(anchor='w', pady=(2, 0))
        controls[key] = check
        mutable.append(check)
        ttk.Label(group, text=description, foreground='#555555', wraplength=790).pack(anchor='w', padx=24, pady=(3, 9))
    ttk.Label(group, text='World Settings startup currently needs exact Food 0.5 in the Ubisoft game folder. '
              'The installer checks this without changing that folder.', wraplength=790).pack(anchor='w', pady=(1, 3))
    ttk.Label(panel, text='Planned: better AI, local-host multiplayer and Knowledge overhaul.',
              foreground='#555555').pack(anchor='w', pady=(12, 8))
    row = ttk.Frame(panel)
    row.pack(fill='x', pady=(0, 12))
    ttk.Label(row, text='Profile name', width=22).pack(side='left')
    entry = ttk.Entry(row, textvariable=name)
    entry.pack(side='left', fill='x', expand=True)
    mutable.append(entry)

    def open_profile():
        file = filedialog.askopenfilename(parent=root, title='Open feature profile', filetypes=[('Feature profiles', '*.json')])
        if file:
            try:
                value = load_profile(file, catalog)
                name.set(value['name'])
                for key, var in flags.items():
                    var.set(value['features'][key])
                refresh()
            except Exception as exc:
                messagebox.showerror('Cannot open profile', str(exc), parent=root)

    def save():
        try:
            value = resolve_selection(selection(), catalog, auto_enable_dependencies=True)
            folder = installer.REPO / 'profiles'
            folder.mkdir(exist_ok=True)
            file = filedialog.asksaveasfilename(parent=root, title='Save feature profile', initialdir=folder,
                                              initialfile='default.json', defaultextension='.json',
                                              filetypes=[('Feature profiles', '*.json')])
            if file:
                save_profile(file, value, catalog, overwrite=Path(file).exists())
                status.set('Feature profile saved.')
        except Exception as exc:
            messagebox.showerror('Cannot save profile', str(exc), parent=root)
    for label, command in (('Open profile', open_profile), ('Save profile', save)):
        button = ttk.Button(row, text=label, command=command)
        button.pack(side='left', padx=(8, 0))
        mutable.append(button)
    summary = tk.Text(panel, height=5, wrap='word', state='disabled', font=('Segoe UI', 10),
                      relief='solid', borderwidth=1, padx=10, pady=8)
    summary.pack(fill='both', expand=True)

    def show_summary(value):
        summary.configure(state='normal')
        summary.delete('1.0', 'end')
        summary.insert('1.0', value)
        summary.configure(state='disabled')
    show_summary('Check installation prepares a plan before any game files change.\n'
                 'Restore returns this installer’s copy to verified original game files and keeps restoration backups.\n'
                 'Restore before changing installed features.')
    ttk.Label(panel, textvariable=status, wraplength=840).pack(anchor='w', pady=(12, 6))
    bar = ttk.Progressbar(panel, mode='indeterminate')
    bar.pack(fill='x', pady=(0, 10))

    def run(kind):
        if busy[0]:
            return
        if not target.get().strip() or (kind in {'check', 'install'} and not source.get().strip()):
            messagebox.showerror('Choose game folders', 'Choose the required game folders first.', parent=root)
            return
        values = (Path(source.get()), Path(target.get()), selection(), Path(provider.get()))
        plan = checked[0]
        busy[0] = True
        for widget in mutable:
            widget.state(['disabled'])
        update_buttons()
        bar.start(16)
        status.set('Working…')
        def worker():
            progress = lambda message: events.put(('progress', str(message)))
            try:
                if kind == 'check':
                    result = installer.check_install(*values[:3], baseline_dir=values[3], progress=progress)
                elif kind == 'install':
                    if plan is None:
                        raise installer.InstallerError('Check the installation first.')
                    result = installer.install(*values[:3], package=Path(plan['package_root']), progress=progress)
                elif kind == 'restore':
                    result = installer.restore(values[1], progress=progress)
                else:
                    installer.launch_world_settings(values[1])
                    result = {'launched': True}
                events.put(('done', (kind, result)))
            except Exception as exc:
                events.put(('error', str(exc)))
        threading.Thread(target=worker, daemon=False).start()

    row = ttk.Frame(panel)
    row.pack(fill='x')
    for key, label in (('check', 'Check installation'), ('install', 'Install selected features'),
                       ('restore', 'Restore original game'), ('start', 'Start with World Settings')):
        button = ttk.Button(row, text=label, command=lambda k=key: run(k))
        button.pack(side='left', padx=(0, 7))
        buttons[key] = button

    def poll():
        last_progress = None
        try:
            while True:
                kind, value = events.get_nowait()
                if kind == 'progress':
                    last_progress = value
                    continue
                busy[0] = False
                bar.stop()
                for widget in mutable:
                    widget.state(['!disabled'])
                if flags['world_settings'].get():
                    controls['food_overhaul'].state(['disabled'])
                if kind == 'error':
                    checked[0] = None
                    status.set('The operation could not finish. See the details above.')
                    show_summary(value)
                else:
                    operation, result = value
                    if operation == 'check':
                        checked[0] = result
                        features = ', '.join(catalog[k].name for k, v in result['profile']['features'].items() if v)
                        action = (f"Create a separate copy ({result['copy_bytes'] / 1024**3:.2f} GB)." if result['creates_copy']
                                  else 'Use the restored original-game copy.')
                        show_summary(f"Ready to install: {features}\n{action}\nDestination: {result['copy_root']}\n"
                                     'Restoration baseline: verified original game. Original installation unchanged.')
                        status.set('Checks passed. Ready to install selected features.')
                    else:
                        checked[0] = None
                        status.set({'install': 'Installation complete.', 'restore': 'Original game files restored. Backups retained.',
                                    'start': 'The automatic World Settings launcher is starting.'}[operation])
                        if operation == 'install':
                            launch_note = ('Use Start with World Settings. World options remain inside Anno.'
                                           if result['profile']['features']['world_settings']
                                           else 'Food-only files are ready. Automatic World Settings startup is disabled.')
                            show_summary('Selected features installed in:\n' + result['copy_root'] + '\n' + launch_note +
                                         '\nRestore before changing installed features.')
                        elif operation == 'restore':
                            show_summary('Verified original game files restored in:\n' + result['copy_root'] +
                                         '\nSaves and backups preserved. Huge-world saves still require World Settings.')
                last_progress = None
                update_buttons()
        except queue.Empty:
            pass
        if last_progress is not None and busy[0]:
            status.set(last_progress)
        root.after(100, poll)

    def close():
        if busy[0]:
            status.set('Please wait for the current operation to finish before closing the installer.')
        else:
            root.destroy()
    for variable in (source, target, provider, name):
        variable.trace_add('write', refresh)
    root.protocol('WM_DELETE_WINDOW', close)
    refresh()
    root.after(100, poll)
    root.mainloop()
