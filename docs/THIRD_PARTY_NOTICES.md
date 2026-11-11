# Third-party notices

## Community policy

[CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md) adapts Contributor Covenant 2.1,
with the enforcement contact method changed for this repository. The policy
retains its separate [Creative Commons Attribution 4.0 International
license](https://creativecommons.org/licenses/by/4.0/), rather than the project
MIT License. Its attribution and related references remain in the policy.
The [official v2.1 source](https://github.com/EthicalSource/contributor_covenant/blob/8a3be1350b07f38b53bbc7073f765a48c4c53ce1/content/version/2/1/code_of_conduct.md)
and [upstream license](https://github.com/EthicalSource/contributor_covenant/blob/8a3be1350b07f38b53bbc7073f765a48c4c53ce1/LICENSE.md)
are pinned to that release.

## Tools in the beta

The standalone Windows beta includes its Python runtime, user-interface
libraries, executable loader, file-analysis libraries and an offline compiler.
It does not distribute Anno game files or prepared mod DLLs.

| Component | Inspected offline version | License text in the beta | Primary reference |
| --- | --- | --- | --- |
| Python | 3.13.4 | `licenses/Python.txt`: Python Software Foundation License Agreement and included notices | [Python Software Foundation](https://www.python.org/psf/) |
| PyInstaller bootloader | 6.16.0 | `licenses/PyInstaller.txt`: GPLv2-or-later with the Bootloader Exception | [PyInstaller](https://pyinstaller.org) |
| pefile | 2024.8.26 | `licenses/pefile.txt`: MIT | [pefile source](https://github.com/erocarrera/pefile) |
| Capstone package | Metadata 5.0.9; the inspected wrapper reports 5.0.7 | `licenses/Capstone.txt`: BSD 3-Clause and included notices | [Capstone](https://www.capstone-engine.org) |
| Tcl/Tk | 8.6.15 / 8.6.15 | `licenses/TclTk.txt`: the installed permissive `license.terms`; the original copy also remains with Tk | No project URL is recorded in the inspected license file. |
| Zig compiler | 0.16.0 | `licenses/Zig.txt` and `tools/compiler/LICENSE`: MIT (Expat) | [Zig](https://ziglang.org/) |

The bundle builder resolves Python package license files through their actual
installed distribution metadata, including user-site installations. It copies
the full license texts, including PyInstaller's Bootloader Exception, without
downloading replacements. Python's license comes from the installed runtime;
Tcl/Tk's license and patch versions come from the files actually collected in
the bundle. Zig's license comes from the reviewed offline compiler.

Each build generates a plain `THIRD_PARTY.txt` and
`licenses/third-party-manifest.json`, recording the actual distribution versions,
license destinations and their SHA256 values. Those files are included in the
complete bundle inventory. The retained launcher cache keeps the license texts
and notices while omitting the compiler itself.
