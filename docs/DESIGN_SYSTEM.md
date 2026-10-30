# JIT-D visual refresh — 2.5

This release adapts the supplied Axion Studio reference to JIT-D's actual product.
The composition uses a light gray canvas, orange accents, generous whitespace,
oversized system typography, pill navigation and actions, rounded cards, and
asymmetric product previews. Agency names, stock imagery, awards and partner
claims are replaced with JIT-D content and clearly labelled workflow illustrations.

## Routes

- `/` — new product home, three editorial sections, two working workspace links.
- `/builder` — visual creation, operation, model connections, hybrid controller,
  receipts and cost calculator, restyled with the selected design language.
- `/studio` — original invoice agent lifecycle and reviewed recovery Studio.
- `/lab` — original workflow lab, also using the shared light theme.
- `/operations` — live system/access status with matching styling.

The home page is a real entry point to the existing application. Its links open
the working tools; its visual cards are illustrations, not invented live results.
All backend functionality and authentication continue to operate through FastAPI.
No external deployment, new API key, model call or paid service is needed to view
or use the offline demonstration. Existing source-policy binding still requires
retesting/publishing older versions when upgrading code in an existing data folder.

## Motion and portability

The orange fluid/fluted-glass hero is an original native WebGL implementation of
the reference's visual direction. It uses locally bundled JavaScript and shaders,
not the reference's React/Vite/npm package stack. This keeps the existing Windows
Python-only startup intact. No stock images, remote fonts, CDN scripts or external
video are required. WebGL failure falls back to a static local CSS composition.

Rendering is capped at 24 fps with bounded pixel density. It pauses when offscreen
or in a hidden tab. Reduced-motion preference renders a single static frame;
workspace transitions also respect reduced motion. Time is displayed in India
using Intl.DateTimeFormat. The home page's mobile navigation has a bottom sheet,
keyboard focus containment and Escape dismissal. All workflow blocks retain
click-to-add and arrow reordering alternatives to dragging.

## Colors

- Main canvas `#EFEFEF` / `#F2F2F0`
- Surfaces `#FFFFFF`
- Charcoal `#181818` / `#20211F`
- Hero accent `#F26522`
- Workspace primary `#C24B15` for readable white labels
- Muted text `#565951`
- Verified state `#287447` on `#EAF3E9`
- Warning state `#88501F` on `#FFF1E3`
- Invalid state `#B5342B` on `#FCECE8`

Orange hero buttons use a dark label for contrast. Semantic success, warning and
failure colors retain distinct meanings; a pleasant design never changes a gate.

The existing plain HTML/CSS/JavaScript views receive shared theme overrides rather
than a framework rewrite. The full source is included in the release ZIP.

## Cursor motion and responsive refinement — 2.5.1

Fine-pointer devices now influence the hero shader's vortex center and glass
ripples through a smoothed pointer uniform. Homepage cards have a small bounded
tilt and local light response; primary home buttons move a few pixels toward the
pointer. Content sections reveal once while scrolling. Workflow nodes, input
fields and their controls are never tilted or magnetized. No custom cursor hides
or replaces the operating system pointer.

Effects run only when appropriate for the device and reduced-motion preference.
Touch/coarse pointers do not receive magnetic or tilt effects. Reduced motion
keeps content visible and renders a static hero frame. The shader is capped at
24 fps on fine pointers and 18 fps on coarse pointers, with existing hidden-tab
and offscreen pauses. Motion uses local JS/CSS and creates no API/model calls.

Phone/tablet navigation uses horizontal rails; builder controls and forms stack
when space is limited. Narrow-screen text fields use 16px input text, navigation
targets are at least 44px high, and node reordering controls have larger targets.
Tables retain their own horizontal scrolling without widening the whole page.
The responsive check covers widths 320/360/390/600/768/900/1024/1440/1920 across
Home, Visual Builder, invoice Studio and System & access. Actual touch/reduced
motion is checked separately from a narrow desktop browser.
