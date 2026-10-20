# WYRD OS: how a phone's operating system works, and how WYRD OS uses it

WYRD OS is the phone in Lagos Island: a Cyberpunk 2077–style handset with WYRD at its core. This document sets out
how a real mobile operating system is put together (from the Android platform documentation and Apple's platform
security guide), then how each idea becomes part of WYRD OS, what is built, and what comes next.

## 1. How a mobile OS is built

A phone's OS is a stack. Each layer only talks to the one under it, which is what keeps it safe and replaceable.

| Layer (real phones) | What it does |
|---|---|
| **Kernel** (Linux on Android, XNU on iOS) | Owns the hardware: memory, processes and threads, power, drivers. Every app is a separate process with its own user ID, so one app can't read another's memory or files (the *sandbox*). |
| **Hardware abstraction layer** | A standard interface to each sensor and radio (camera, GPS, Bluetooth). The system loads a module when something asks for that hardware. |
| **Runtime** | Runs the apps' code (ART on Android, each app in its own process), with garbage collection and crash reporting. |
| **System services / framework** | The managers every app uses: the *activity manager* (app lifecycle and the back stack), the *notification manager*, the *permission manager*, the window manager, content providers for sharing data. |
| **System UI** | What you see that isn't an app: the lock screen, the status bar, the notification shade, quick settings / control centre, the home screen, the navigation bar, the Dynamic Island / live activities. |
| **Apps** | System apps and user apps use the same framework. |

### The parts that shape how a phone *feels*

- **Lifecycle.** An app is *created → started → resumed* (in front, taking input) → *paused* (still visible, not in front) → *stopped* (out of sight) → *destroyed*. When memory runs short the OS kills processes, background ones first, so an app saves its state when it goes out of sight and restores it when you come back. Back walks a *back stack*; Home leaves the app running in the background.
- **Notifications.** Each app posts to *channels* with an importance (high pops up as a heads-up banner, low stays quiet). Each notification has a *lock-screen visibility*: **public** (shown in full), **private** (only "Messages · 1 new" until you unlock), or **secret** (not shown at all). They group, and carry actions (Reply, Mark read) that work without opening the app.
- **Permissions.** Harmless access is granted when an app is installed. Sensitive access (location, camera, microphone, contacts) is asked for *at the moment it's needed*, can be allowed *once*, and is revoked automatically for apps left unused. The user can see and change all of it in Settings.
- **Lock and data protection.** The passcode doesn't just hide the screen: it's part of the key that encrypts your data, so with the phone locked the data stays sealed. Guessing is slowed by the hardware (a secure enclave) with **escalating delays**: on iPhone, three free attempts, then 1 minute rising to 8 hours by the ninth, and optionally erase after ten. Biometrics (face, fingerprint) make a strong passcode painless. Only a few things work while locked: the camera, media controls, emergency calls, and notifications at their chosen visibility.
- **Live activities / Dynamic Island.** An ongoing task (music, a ride, a timer, a flight) shows compactly round the camera cutout: an icon on one side and its state on the other. A long press expands it, and a tap opens the app.

## 2. WYRD OS, layer by layer

| Real layer | In WYRD OS |
|---|---|
| Kernel | **The WYRD server** (Serverpod): it owns the truth, which is your Naira, your home, your career and the ledger. The phone never decides money or scores (the Grid and flights are checked on the server). |
| Hardware abstraction | **The island's senses**: the live Lagos weather (airport METAR), NEPA power (the light), your position on the map, the clock. Apps ask for these and never invent them. |
| Runtime | The page: one process. Each app is a `render(app)` with its own state. |
| System services | `go()` / `stack` (the activity manager and back stack), `notify()` (the notification manager), the token and keys (the keystore: end-to-end chat keys stay in this browser). |
| System UI | Boot, the **lock screen**, the status bar, the **notification shade**, the home widgets and dock, the **Dynamic Island**, the **navigation bar**, the side **power button**. |
| Apps | Wallet, Jobs, Link, My HQ, Arena, Casino, WYRD, Ride, **Airport**, Garage, Stores, Homes, Parties, Fashion, Music, Government, Grid, Profile, Privacy, Credits. |

WYRD itself is the assistant built into the OS. It reads your situation (the weather, the power, your shift, your
home) and explains, but it never moves money or changes a score. That matches the real OS rule: the assistant
gets no permission the user hasn't given.

## 3. Built in this update (WYRD OS 3)

- **System states.** The phone is *asleep* (put away), *locked* (the lock screen) or *unlocked*. While locked,
  **Back, Home and Close are idle** (dimmed, no taps); only the lock screen's own controls answer: unlock, the
  quick buttons and the music controls. The **side button is the power button** and puts the phone away in any
  state. Esc does the same on a computer.
- **Lock screen, Night City over Lagos.** Scanlines, a glitching neon clock, a *NETWATCH · LINK SECURE* status chip,
  the live Lagos weather, what's playing, and your latest notifications. **Swipe up (or tap) to unlock**: *WYRD ID //
  NEURAL MATCH* runs its scan, a beam goes up the screen and the lock screen lifts away. The quick buttons (Ride,
  Music, WYRD) unlock straight into that app.
- **Dynamic Island as live activities.** Compact (*what* on the left, *how it's going* on the right):
  - music, with its cover and a moving equaliser;
  - **your flight** (✈️ LOS → DXB and a countdown);
  - **your Grid shift** (⚡ the task and 1/3);
  - the city DJ (LIVE) and your ride.

  When locked, it shows a padlock that scans while you unlock, then flashes **WYRD ID ✓**. When idle, WYRD's orb
  breathes in the notch. Notifications still grow out of it for a moment.
- **Light on the device.** All of it is CSS transforms and opacity (handled by the graphics chip) and one timer
  twice a second. It respects *reduce motion*.

## 4. Next, in order

1. **Notification privacy on the lock screen** (*public / private / secret* per app channel). Default: private, so
   chats show "💬 Link · 1 new message" until you unlock. Settings → Notifications to choose per app.
2. **Control centre** (swipe down from the top right): Wi-Fi/link, sound, music, brightness/night shift, Do Not
   Disturb, the torch (lights the street round you at night), a screen recording of your island.
3. **App lifecycle done properly**: apps keep their state when you go Home and come back (the scroll, a half-typed
   chat), and an **app switcher** (swipe up and hold) of your recent apps as cards.
4. **Permissions sheet**: the first time an app wants something sensitive (your location for Ride, the microphone
   for WYRD voice), WYRD OS asks: *Allow once / While using / Don't allow*. Settings → Privacy lists every grant.
5. **Long-press the island** to expand a live activity (the flight's progress map, the shift's task list, the
   music's scrubber).
6. **Cyberware look**: an optional "Kiroshi" HUD theme (scan lines, tactical overlays on the map when the phone is
   open), the glitch on errors, and an OS sound set.

## 5. Lock-screen security: options to decide together

| Option | What the player gets | Notes |
|---|---|---|
| **A. No lock (now)** | Swipe and you're in | The phone sits behind your account sign-in already |
| **B. PIN (4 or 6 digits)** | A keypad on the lock screen | Kept on the device, salted and hashed; escalating delays after 3 wrong tries (1 min → 5 → 15 → 60), as on a real phone |
| **C. Pattern** | A 3×3 neon grid, Cyberpunk-style | Same storage and delays as the PIN; easy to watch over a shoulder |
| **D. Device biometrics (WebAuthn / passkey)** | Face ID / fingerprint unlocks *WYRD ID* for real | The browser's own secure hardware; nothing biometric reaches us. Strongest and quickest |
| **E. Lock the money only** | Wallet, withdrawals and sending Naira ask for the PIN / biometric; the rest stays open | Fits how players use it: protects what matters, little friction |
| **F. Auto-lock** | The phone locks after N minutes away or when the tab is hidden | Pairs with any of B–E |
| **G. Lockdown on many failures** | After 10 wrong tries, sign in again with the account password | Instead of erasing (there's nothing on the phone to erase) |

Recommended: **D with B as the fallback, plus E and F**. Real Face ID / fingerprint through the browser, a PIN when
the device has none, the money behind it, auto-lock after 5 minutes, and lockdown after 10 failures. Notification
privacy (Next 1) comes with it.

---
Sources: Android platform architecture (developer.android.com/guide/platform); Activity lifecycle
(developer.android.com/guide/components/activities/activity-lifecycle); Notifications and Permissions overviews
(developer.android.com); Apple Platform Security, *Passcodes and passwords* (support.apple.com/guide/security).
