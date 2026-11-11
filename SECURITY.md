# Security policy

## Supported versions

Security fixes are focused on the latest published beta, currently
**0.9.0-beta.1**. Earlier development builds are retained for reference and are
not maintained as separate security-support branches.

The public beta supports World Settings on the inspected **AMD64 Anno 1503
History Edition build with Dutch scene and UI data**. Food 0.5 and its combined
development profile remain experimental. Other game builds and localizations
are outside the verified compatibility scope. See the
[beta validation record](docs/BETA_VALIDATION.md).

## Report a vulnerability privately

Use GitHub's **Report a vulnerability** option on this repository's Security
tab when it is available:

<https://github.com/GOjayson/anno1503-grand-overhaul/security/advisories/new>

Do not put exploit details or sensitive attachments in a public issue, pull
request or discussion. If private reporting is unavailable, open an issue
containing only a request for a private security contact. Wait for the
maintainer to arrange a channel before sharing details. No separate security
email address is currently published.

Include the affected mod version, component, game edition/build and selected
features; describe the impact and the smallest safe reproduction. Explain
whether you observed the problem in a game run or inferred it from source or
an automated check. Reproduce on a separate copy and preserve existing saves
and backups.

Never post Ubisoft launch arguments, authentication data, account details,
credentials, complete game files, native saves, memory dumps or unredacted
logs. A maintainer can discuss what sanitized evidence is needed privately.
Ordinary gameplay bugs belong in the public [issue
chooser](https://github.com/GOjayson/anno1503-grand-overhaul/issues/new/choose).

## Handling reports

The maintainer will review reports and coordinate any fix and disclosure with
the reporter where possible. This community project does not promise a fixed
response or resolution time. Please allow a private investigation before
publishing vulnerability details.

The installer verifies supported input files and uses a separate managed game
copy with restoration records. Native activation checks the exact process,
modules and patch preimages. These guards reduce known risks; they are not a
security guarantee. Do not bypass a failed compatibility or activation check,
disable security software, or upload authentication material to obtain help.
