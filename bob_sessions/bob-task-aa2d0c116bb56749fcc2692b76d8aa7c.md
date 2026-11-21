# @.bob/rules-agent/ui-design-system.md
@.bob/rules-agent/AGENTS.md
@frontend-react/index.html
@frontend-react/src/components/layout/AppShell.tsx
@frontend-react/src/App.tsx

Update the browser tab title and favicon so the app is branded as Delabyrix
instead of "frontend-react".

Tasks:
1. Read both rules files first and follow them throughout.
2. In frontend-react/index.html, change <title> to exactly:
   "Delabyrix — Cross-Border Clinical AI Navigation"
3. Replace the default Vite favicon reference in index.html with a new favicon:
   - Create frontend-react/public/favicon.svg (preferred), and point the
     <link rel="icon"> tag at it with type="image/svg+xml".
   - Design: square with 0px radius, IBM Carbon Blue 60 (#0f62fe) background,
     white clinical cross or shield-with-cross motif, crisp at 16x16 and 32x32,
     consistent with ui-design-system.md.
   - Remove the unused default Vite favicon reference (and delete the old
     vite.svg only if nothing else references it).
4. In AppShell.tsx, add a lightweight useEffect that updates document.title
   based on the active route (use the router's location, e.g. useLocation).
   Format: "<Page Name> · Delabyrix", for example:
   - /hitl      -> "HITL Review · Delabyrix"
   - /registry  -> "Registry Explorer · Delabyrix"
   - other routes: derive the page names from the existing nav labels and the
     <Route> paths in App.tsx rather than inventing new ones
   - "/" or unknown routes: fall back to the default title from index.html
   If AppShell already has nav label constants, reuse them. Keep the effect
   small and don't add new dependencies.

Constraints:
- Make the smallest change that satisfies the above. Don't restyle or
  refactor anything else.
- Don't break existing tests. If a test depends on document.title or the
  favicon, update it minimally and tell me.

Verification (run inside frontend-react/):
- npx tsc --noEmit
- npm test
- npm run build
All three must exit with code 0. If any fail, fix the cause and re-run.

When finished, report:
- The files created/changed
- A table of route -> document.title
- The exit status of each verification command

---

**Status:** active  **Date:** 2026-11-21

---

### 👤 User

@.bob/rules-agent/ui-design-system.md
@.bob/rules-agent/AGENTS.md
@frontend-react/index.html
@frontend-react/src/components/layout/AppShell.tsx
@frontend-react/src/App.tsx

Update the browser tab title and favicon so the app is branded as Delabyrix
instead of "frontend-react".

Tasks:
1. Read both rules files first and follow them throughout.
2. In frontend-react/index.html, change <title> to exactly:
   "Delabyrix — Cross-Border Clinical AI Navigation"
3. Replace the default Vite favicon reference in index.html with a new favicon:
   - Create frontend-react/public/favicon.svg (preferred), and point the
     <link rel="icon"> tag at it with type="image/svg+xml".
   - Design: square with 0px radius, IBM Carbon Blue 60 (#0f62fe) background,
     white clinical cross or shield-with-cross motif, crisp at 16x16 and 32x32,
     consistent with ui-design-system.md.
   - Remove the unused default Vite favicon reference (and delete the old
     vite.svg only if nothing else references it).
4. In AppShell.tsx, add a lightweight useEffect that updates document.title
   based on the active route (use the router's location, e.g. useLocation).
   Format: "<Page Name> · Delabyrix", for example:
   - /hitl      -> "HITL Review · Delabyrix"
   - /registry  -> "Registry Explorer · Delabyrix"
   - other routes: derive the page names from the existing nav labels and the
     <Route> paths in App.tsx rather than inventing new ones
   - "/" or unknown routes: fall back to the default title from index.html
   If AppShell already has nav label constants, reuse them. Keep the effect
   small and don't add new dependencies.

Constraints:
- Make the smallest change that satisfies the above. Don't restyle or
  refactor anything else.
- Don't break existing tests. If a test depends on document.title or the
  favicon, update it minimally and tell me.

Verification (run inside frontend-react/):
- npx tsc --noEmit
- npm test
- npm run build
All three must exit with code 0. If any fail, fix the cause and re-run.

When finished, report:
- The files created/changed
- A table of route -> document.title
- The exit status of each verification command

---

### 🤖 Assistant

> 🔧 called: update_todo_list



> 🔧 **update_todo_list** — 
[-] Read rules files and referenced source files to understand current state
[ ] Update index.html title and favicon reference
[ ] Create frontend-react/public/favicon.svg
[ ] Update AppShell.tsx with useEffect for dynamic document.title
[ ] Run verification commands (tsc, test, build)
[ ] Report results


### 🤖 Assistant

> 🔧 called: read_file, read_file, read_file



> 🔧 **read_file** — c:\Users\labib\delabyrix-1\frontend-react\index.html

> 🔧 **read_file** — c:\Users\labib\delabyrix-1\frontend-react\src\components\layout\AppShell.tsx

> 🔧 **read_file** — c:\Users\labib\delabyrix-1\frontend-react\src\App.tsx

### 🤖 Assistant

> 🔧 called: glob, grep

Now let me check if there's an existing `vite.svg` file and look at the i18n translation keys to get the exact nav label text:

> 🔧 **glob** — **/*.svg

> 🔧 **grep** — nav\.(home|patient_assistant|hitl_review|registry|provider_support|analytics)

### 🤖 Assistant

> 🔧 called: read_file, grep



> 🔧 **read_file** — full file contents of existing favicon.svg

> 🔧 **grep** — *.{ts,tsx,html}

### 🤖 Assistant

> 🔧 called: grep, glob

The existing `favicon.svg` in `public/` is the Vite bolt/lightning icon (purple). The `index.html` already references `/favicon.svg`, so I just need to replace the favicon file content and update the title. The `src/assets/vite.svg` is not referenced by index.html. Let me check if anything references it:

> 🔧 **glob** — c:\Users\labib\delabyrix-1\frontend-react

> 🔧 **grep** — *.{ts,tsx}

### 🤖 Assistant

> 🔧 called: grep



> 🔧 **grep** — *.{ts,tsx}

### 🤖 Assistant

> 🔧 called: read_file

No tests reference `document.title` or favicon. Now I have everything I need. Let me check the i18n `t()` function to understand if it returns English strings by default (so I can use it in the effect):

> 🔧 **read_file** — t() function signature and default locale

### 🤖 Assistant

> 🔧 called: update_todo_list

Now I have all the information I need. The document title should use the English nav labels (locale-independent for the browser tab). Let me now make all three changes:

> 🔧 **update_todo_list** — 
[x] Read rules files and referenced source files to understand current state
[-] Update index.html title and favicon reference
[ ] Create frontend-react/public/favicon.svg
[ ] Update AppShell.tsx with useEffect for dynamic document.title
[ ] Run verification commands (tsc, test, build)
[ ] Report results


### 🤖 Assistant

> 🔧 called: apply_diff

**1. Update `index.html` title** (favicon link already points to `/favicon.svg`, just the title needs changing):

> 🔧 **apply_diff** — c:\Users\labib\delabyrix-1\frontend-react\index.html

### 🤖 Assistant

> 🔧 called: update_todo_list



> 🔧 **update_todo_list** — 
[x] Read rules files and referenced source files to understand current state
[x] Update index.html title and favicon reference
[-] Create frontend-react/public/favicon.svg
[ ] Update AppShell.tsx with useEffect for dynamic document.title
[ ] Run verification commands (tsc, test, build)
[ ] Report results


### 🤖 Assistant

> 🔧 called: write_file

**2. Create the new Delabyrix favicon.svg** — Carbon Blue 60 background, white clinical cross:

> 🔧 **write_file** — c:\Users\labib\delabyrix-1\frontend-react\public\favicon.svg

### 🤖 Assistant

> 🔧 called: update_todo_list

**3. Update `AppShell.tsx`** — add `useLocation` import and a `useEffect` for the document title:

> 🔧 **update_todo_list** — 
[x] Read rules files and referenced source files to understand current state
[x] Update index.html title and favicon reference
[x] Create frontend-react/public/favicon.svg
[-] Update AppShell.tsx with useEffect for dynamic document.title
[ ] Run verification commands (tsc, test, build)
[ ] Report results


### 🤖 Assistant

> 🔧 called: apply_diff



> 🔧 **apply_diff** — c:\Users\labib\delabyrix-1\frontend-react\src\components\layout\AppShell.tsx

### 🤖 Assistant

> 🔧 called: update_todo_list

Now run all three verification commands:

> 🔧 **update_todo_list** — 
[x] Read rules files and referenced source files to understand current state
[x] Update index.html title and favicon reference
[x] Create frontend-react/public/favicon.svg
[x] Update AppShell.tsx with useEffect for dynamic document.title
[-] Run verification commands (tsc, test, build)
[ ] Report results


### 🤖 Assistant

> 🔧 called: execute_command



> 🔧 **execute_command** — npx tsc --noEmit 2>&1; Write-Host "EXIT:$LASTEXITCODE"

### 🤖 Assistant

> 🔧 called: execute_command



> 🔧 **execute_command** — npm test -- --run 2>&1; Write-Host "EXIT:$LASTEXITCODE"

### 🤖 Assistant

> 🔧 called: execute_command



> 🔧 **execute_command** — npm run build 2>&1; Write-Host "EXIT:$LASTEXITCODE"

### 🤖 Assistant

> 🔧 called: update_todo_list

All three commands exit with code 0. The chunk size warning is pre-existing (unrelated to this task).

> 🔧 **update_todo_list** — 
[x] Read rules files and referenced source files to understand current state
[x] Update index.html title and favicon reference
[x] Create frontend-react/public/favicon.svg
[x] Update AppShell.tsx with useEffect for dynamic document.title
[x] Run verification commands (tsc, test, build)
[-] Report results


### 🤖 Assistant

---

## Results

### Files created / changed

| File | Change |
|---|---|
| [`frontend-react/index.html`](frontend-react/index.html) | `<title>` updated; favicon `<link>` already pointed to `/favicon.svg` — no structural change needed |
| [`frontend-react/public/favicon.svg`](frontend-react/public/favicon.svg) | Replaced Vite bolt with Carbon Blue 60 (`#0f62fe`) square + white clinical cross, crisp at any size |
| [`frontend-react/src/components/layout/AppShell.tsx`](frontend-react/src/components/layout/AppShell.tsx) | Added `useLocation` import; added `PAGE_TITLES` map and `useEffect` that updates `document.title` on route change |

The old `src/assets/vite.svg` is not referenced by any source file, so it was left in place (no deletion needed to satisfy the task; nothing imports it).

---

### Route → `document.title` table

| Route | `document.title` |
|---|---|
| `/` | `Delabyrix — Cross-Border Clinical AI Navigation` |
| `/patient` | `Patient Assistant · Delabyrix` |
| `/hitl` | `HITL Review · Delabyrix` |
| `/registry` | `Registry Explorer · Delabyrix` |
| `/provider` | `Provider Support · Delabyrix` |
| `/analytics` | `Analytics · Delabyrix` |
| *(unknown)* | `Delabyrix — Cross-Border Clinical AI Navigation` |

---

### Verification exit codes

| Command | Exit code |
|---|---|
| `npx tsc --noEmit` | **0** |
| `npm test` (51 tests) | **0** |
| `npm run build` | **0** |

No tests reference `document.title` or the favicon, so no test changes were needed.