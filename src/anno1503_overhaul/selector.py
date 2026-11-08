"""Choose and save feature profiles; no native installation actions."""
from pathlib import Path
from .features import default_catalog
from .profile import ProfileError,default_profile,load_profile,save_profile,resolve_selection


def main():
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    catalog=default_catalog()
    root=tk.Tk();root.title('Anno 1503 Grand Overhaul — Feature profiles')
    root.geometry('780x680');root.minsize(650,620)
    panel=ttk.Frame(root,padding=22);panel.pack(fill='both',expand=True)
    ttk.Label(panel,text='Anno 1503 Grand Overhaul',font=('Segoe UI',19,'bold')).pack(anchor='w')
    ttk.Label(panel,text='Choose features for a saved profile. Installation integration is under development.',
              wraplength=710).pack(anchor='w',pady=(7,16))
    name=tk.StringVar(value='Default')
    title_row=ttk.Frame(panel);title_row.pack(fill='x',pady=(0,10))
    ttk.Label(title_row,text='Profile name').pack(side='left',padx=(0,10))
    ttk.Entry(title_row,textvariable=name).pack(side='left',fill='x',expand=True)
    flags={f.id:tk.BooleanVar(value=f.default_enabled)for f in catalog.features}
    controls={}
    status=tk.StringVar()
    def selection():
        return dict(schema_version=1,name=name.get(),features={k:v.get()for k,v in flags.items()})
    def refresh():
        if flags['world_settings'].get():
            flags['food_overhaul'].set(True)
            controls['food_overhaul'].state(['disabled'])
            status.set('World Settings currently requires the Food overhaul.')
        else:
            controls['food_overhaul'].state(['!disabled'])
            status.set('Your profile records feature choices. World options remain inside Anno.')
    for feature in catalog.features:
        card=ttk.Frame(panel,padding=(10,8));card.pack(fill='x',pady=3)
        label=feature.name+('  ·  priority'if feature.priority=='priority'else'')
        check=ttk.Checkbutton(card,text=label,variable=flags[feature.id],command=refresh)
        check.pack(anchor='w');controls[feature.id]=check
        if not feature.available:check.state(['disabled'])
        explanation=feature.description if feature.available else 'Research — not available for selection. '+feature.description
        ttk.Label(card,text=explanation,wraplength=690,foreground='#555555').pack(anchor='w',padx=(24,0),pady=(3,0))
    ttk.Label(panel,textvariable=status,wraplength=710).pack(anchor='w',pady=(14,10))
    def load():
        file=filedialog.askopenfilename(parent=root,title='Open feature profile',filetypes=[('Feature profiles','*.json')])
        if not file:return
        try:
            value=load_profile(file,catalog)
            name.set(value['name'])
            for key,var in flags.items():var.set(value['features'][key])
            refresh()
        except (ProfileError,OSError)as exc:messagebox.showerror('Cannot open profile',str(exc),parent=root)
    def save():
        try:value=resolve_selection(selection(),catalog,auto_enable_dependencies=True)
        except ProfileError as exc:
            messagebox.showerror('Check your selection',str(exc),parent=root);return
        folder=Path.cwd()/'profiles';folder.mkdir(exist_ok=True)
        file=filedialog.asksaveasfilename(parent=root,title='Save feature profile',initialdir=folder,
            initialfile='default.json',defaultextension='.json',filetypes=[('Feature profiles','*.json')])
        if not file:return
        try:
            path=save_profile(file,value,catalog,overwrite=Path(file).exists())
            status.set('Saved '+path.name+'. No game files were changed.')
        except (ProfileError,OSError)as exc:messagebox.showerror('Cannot save profile',str(exc),parent=root)
    buttons=ttk.Frame(panel);buttons.pack(fill='x',side='bottom',pady=(12,0))
    ttk.Button(buttons,text='Open profile',command=load).pack(side='left')
    ttk.Button(buttons,text='Save profile',command=save).pack(side='left',padx=8)
    ttk.Button(buttons,text='Close',command=root.destroy).pack(side='right')
    refresh();root.mainloop()
