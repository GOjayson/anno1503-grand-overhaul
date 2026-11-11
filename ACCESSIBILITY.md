# Accessibility

Anno 1503 Grand Overhaul aims to make its installer and in-game settings easier
to understand and operate. Accessibility improvements are welcome alongside
the current World Settings work. This statement is not a claim of conformance
with an accessibility standard.

## Current scope

The current public beta is **0.9.0-beta.1**, for the inspected **64-bit Windows
History Edition build with Dutch scene and UI data**. The mod's setup text is
in English. Other localizations and platform combinations need verification.

The installer uses Windows-hosted Tk controls with text labels, checkboxes and
buttons. World Settings uses Win32 controls with labels and keyboard focus
stops. Presets can reduce the number of settings a player needs to enter
repeatedly. These implementation choices do not establish that complete
keyboard-only or screen-reader workflows work correctly.

The mod does not replace Anno's underlying menus, camera controls, gameplay
interface or audio. Their accessibility remains constrained by the base game.

## Known limitations and testing gaps

- The island preview uses visual shapes and colors. Inspecting or choosing a
  particular island currently uses a map click. Textual island details and a
  labeled legend supplement the preview; a complete nonvisual map workflow has
  not been validated.
- The installer has a minimum window size, and World Settings uses a fixed
  layout. Small screens, large text and different display scaling may expose
  clipping or difficult-to-reach controls. Those combinations have not been
  comprehensively tested.
- Screen-reader announcements, keyboard focus order, high-contrast modes,
  color-vision alternatives and assistive-input compatibility have not had a
  systematic accessibility audit. No broad compatibility claim is made for
  those tools or modes.

Visual layout checks and successful game runs recorded in the
[beta validation record](docs/BETA_VALIDATION.md) are not accessibility testing.

## Report a barrier

Choose an accessibility report in the [issue
chooser](https://github.com/GOjayson/anno1503-grand-overhaul/issues/new/choose).
Describe the task you were trying to complete, where the barrier occurred,
what happened and what would have helped. Include the mod version and, when
relevant, your Windows version, display scaling and assistive technology with
its version. Include only information you are comfortable making public.

Suggestions for clearer labels, better focus behavior, readable layouts and
alternatives to visual-only interaction are welcome. You do not need to supply
a code change or prove conformance with a standard to report a barrier. If a
report contains security-sensitive details, follow [the security
policy](SECURITY.md) instead of posting them publicly.
