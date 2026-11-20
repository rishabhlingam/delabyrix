---
description: IBM Carbon tokens and shadcn/ui conventions for product UI
globs: frontend/**/*.{tsx,css}
alwaysApply: true
---

# IBM Carbon + shadcn/ui

Product UI is shadcn/ui `radix-nova` primitives restyled to IBM Carbon. There is no `tailwind.config.*`. Tailwind v4 reads `src/index.css` (`components.json` sets `"config": ""` and `"css": "src/index.css"`).

When adding UI, compose `@/components/ui/*` and override radius, border, and color on the instance. Do not restyle the primitive files to match one screen.

`components.json`: `style` `radix-nova`, `rsc` false, `tsx` true, `baseColor` `neutral`, `cssVariables` true, `prefix` `""`, `iconLibrary` `lucide`. Aliases: `@/components`, `@/components/ui`, `@/lib`, `@/lib/utils`, `@/hooks`. Class merging imports `cn` from the `cn` package (`src/lib/utils.ts` only re-exports it).

## CSS entry

Keep this import order in `src/index.css`:

```css
@import "@ibm/plex/css/ibm-plex.min.css";
@import "tailwindcss";
@import "tw-animate-css";
@import "shadcn/tailwind.css";

@custom-variant dark (&:is(.dark *));
```

`:root` holds the raw values. `@theme inline` exposes them as Tailwind colors, fonts, and radii. `@layer base` sets the document font, page color, and default border. No `.dark` token block exists. Do not invent a dark palette.

## Color and layer variables

Use these tokens for chrome. Hex values below are the ones in `:root`.

| Token | Value | Role |
| --- | --- | --- |
| `--background` | `#f4f4f4` | Page (Carbon Gray 10) |
| `--foreground` | `#161616` | Text (Carbon Gray 100) |
| `--card` / `--popover` | `#ffffff` | Surface (Carbon Layer 01) |
| `--card-foreground` / `--popover-foreground` | `#161616` | Text on surface |
| `--primary` | `#0f62fe` | Carbon Blue 60 |
| `--primary-foreground` | `#ffffff` | Text on primary |
| `--secondary` | `#e0e0e0` | Neutral fill |
| `--secondary-foreground` | `#161616` | Text on secondary |
| `--muted` | `#e5e5e5` | Commented in source as Carbon Gray 20 |
| `--muted-foreground` | `#525252` | Carbon Gray 70 |
| `--accent` | `#edf5ff` | Blue tint |
| `--accent-foreground` | `#0043ce` | Blue text on tint |
| `--destructive` | `#da1e28` | Carbon Red 60 |
| `--border` / `--input` | `#e0e0e0` | Carbon border subtle |
| `--ring` | `#0f62fe` | Focus |
| `--chart-1` … `--chart-5` | `#0f62fe`, `#24a148`, `#f1c21b`, `#da1e28`, `#8a3ffc` | Defined; unused on current screens |
| `--sidebar` | `#f4f4f4` | Same Gray 10 scale as the page |
| `--sidebar-foreground` | `#161616` | |
| `--sidebar-primary` | `#0f62fe` | |
| `--sidebar-primary-foreground` | `#ffffff` | |
| `--sidebar-accent` | `#e5e5e5` | |
| `--sidebar-accent-foreground` | `#161616` | |
| `--sidebar-border` | `#e0e0e0` | |
| `--sidebar-ring` | `#0f62fe` | |

`@theme inline` maps each token to a Tailwind color (`--color-primary: var(--primary)`, and the same for background, foreground, card, popover, secondary, muted, accent, destructive, border, input, ring, chart, sidebar). Prefer `bg-background`, `text-foreground`, `bg-card`, `border-border`, `text-muted-foreground`, `bg-primary` when the semantic token matches. Product screens also use the Carbon hexes below, which are not all tokens.

| Hex | Use |
| --- | --- |
| `#ffffff` | Card, header, response well |
| `#f4f4f4` | Page, inquiry well, sheet header. Header wash is `bg-[#f4f4f4]/60`. Footer wash is `bg-[#f4f4f4]/40` |
| `#e0e0e0` | 1px borders and separators |
| `#8d8d8d` | Card border on hover (Carbon Gray 50) |
| `#c6c6c6` | PII pill border (Carbon Gray 30) |
| `#e5e5e5` | PII pill fill |
| `#525252` | Meta text |
| `#161616` | Body text |
| `#0f62fe` | Brand, links, primary button |
| `#0353e9` | Primary button hover (Carbon Blue 60 hover) |
| `#edf5ff` | Link / ghost hover, jurisdiction fill |
| `#a6c8ff` | Jurisdiction border |
| `#0043ce` | Jurisdiction text, ghost hover text |
| `#f1c21b` | Pending stripe and badge border |
| `#fcf4d6` | Pending badge fill |
| `#b28600` | Pending icon |
| `#24a148` | Approved stripe, badge border, icon |
| `#defbe6` | Approved badge fill |
| `#0e6027` | Approved badge text |
| `#da1e28` | Rejected stripe, badge border, icon, risk flag, reject button |
| `#fff1f1` | Rejected badge fill, risk flag fill |
| `#a2191f` | Rejected badge text |

`@layer base` applies `border-border` and `outline-ring/50` on `*`, sets `body` to IBM Plex Sans on `var(--background)` / `var(--foreground)`, and sets `html` to `font-sans`.

## Border radius

`--radius` is `0px`. The scale is all zero:

```css
--radius-sm: calc(var(--radius) * 0.6);
--radius-md: calc(var(--radius) * 0.8);
--radius-lg: var(--radius);
--radius-xl: calc(var(--radius) * 1.4);
--radius-2xl: calc(var(--radius) * 1.8);
--radius-3xl: calc(var(--radius) * 2.2);
--radius-4xl: calc(var(--radius) * 2.6);
```

Keep `--radius: 0px`. Primitives still ship with `rounded-xl` (card), `rounded-lg` (button), and `rounded-4xl` (badge). Those utilities resolve to 0 through the theme, and product instances also set `rounded-none` so a primitive default cannot bring corners back. Apply `rounded-none` on product cards, badges, buttons, sheets, and wells. Do not add `rounded-md`, `rounded-lg`, `rounded-full`, or arbitrary radii.

## Typography

Fonts come from `@ibm/plex`. Theme:

```css
--font-heading: "IBM Plex Sans", sans-serif;
--font-sans: "IBM Plex Sans", sans-serif;
--font-mono: "IBM Plex Mono", monospace;
```

`code`, `pre`, and `.font-mono` use IBM Plex Mono.

| Role | Classes |
| --- | --- |
| Brand line | `text-xs font-semibold tracking-wide text-[#0f62fe]` |
| Page title | `text-base font-medium text-[#161616]` |
| Section label | `text-xs font-semibold uppercase tracking-wider text-[#525252]` |
| Body | `text-sm leading-relaxed text-[#161616]` |
| Metadata, ids, counts, timestamps | `font-mono text-xs text-[#525252]` with `tabular-nums` on counts and times |
| Card title primitive | `font-heading text-base leading-snug font-medium` |
| Sheet title | `font-heading text-base font-medium` |

Use `font-mono` for record ids, model ids, timestamps, jurisdiction badges, audit descriptions, and `[REDACTED_*]` pills. Use Plex Sans for titles, labels, and prose.

## Icons

Domain and action icons come from `@carbon/icons-react`. Size them at `h-3.5 w-3.5` and separate them from the label with `mr-1` or `mr-1.5`.

Icons in use: `CheckmarkFilled`, `CloseFilled`, `WarningAltFilled`, `Security`, `Translate`, `Time`, `DocumentView`.

Status icon colors: pending `#b28600`, approved `#24a148`, rejected `#da1e28`.

`components.json` sets `iconLibrary` to `lucide`. Lucide stays inside generated shadcn chrome (the sheet close control uses `XIcon` from `lucide-react`). Do not put Lucide icons on product actions.

## Status badges

Use `Badge` with `variant="outline"` plus `h-auto rounded-none px-2 py-0.5 text-xs font-medium` and the status classes. Pair the badge with a `border-l-4` stripe in the same hue.

| Status | Stripe | Badge classes | Icon |
| --- | --- | --- | --- |
| `PENDING` | `border-l-[#f1c21b]` | `bg-[#fcf4d6] text-[#161616] border-[#f1c21b]` | `WarningAltFilled` in `#b28600` |
| `APPROVED` | `border-l-[#24a148]` | `bg-[#defbe6] text-[#0e6027] border-[#24a148]` | `CheckmarkFilled` in `#24a148` |
| `REJECTED` | `border-l-[#da1e28]` | `bg-[#fff1f1] text-[#a2191f] border-[#da1e28]` | `CloseFilled` in `#da1e28` |

Jurisdiction is a second outline badge: `rounded-none border-[#a6c8ff] bg-[#edf5ff] font-mono text-xs font-normal text-[#0043ce]`, with `Security`.

A risk flag is not a `Badge`. It is `inline-flex items-center bg-[#fff1f1] px-2 py-0.5 text-xs font-medium text-[#da1e28]` with `WarningAltFilled`.

PII tokens are not badges. Render them as `border border-[#c6c6c6] bg-[#e5e5e5] px-1.5 py-0.5 font-mono text-xs font-medium text-[#161616]`.

## Card elevation

Cards are flat. The shadcn `Card` default is `ring-1 ring-foreground/10` and `rounded-xl`, with no shadow. Product cards turn that off:

`gap-0 rounded-none border border-[#e0e0e0] bg-white py-0 shadow-none ring-0`

Hover uses `hover:border-[#8d8d8d]`, not a shadow. Status is the 4px left border, not elevation. Separate header, body, and footer with `Separator` at `bg-[#e0e0e0]`.

The card footer primitive adds `border-t bg-muted/50`. Product footers replace that with `rounded-none border-0 bg-[#f4f4f4]/40`.

The sheet is the only elevated surface. `SheetContent` uses `shadow-lg`. Product sheets add `rounded-none border-[#e0e0e0] bg-white sm:max-w-md`.

## Layout spacing

| Region | Classes |
| --- | --- |
| Page | `min-h-svh bg-background text-foreground` |
| Column | `mx-auto max-w-3xl px-4` |
| Header | `border-b border-[#e0e0e0] bg-white`; inner row `gap-4 py-3` |
| Main stack | `flex flex-col gap-4 py-6` |
| Card header | `px-4 py-3`, row `gap-2`, clusters `gap-3`. Wash: `bg-[#f4f4f4]/60` |
| Card body | `space-y-4 p-4`. Label margin `mb-1.5`. Wells `border border-[#e0e0e0] p-3` |
| Card footer | `px-4 py-2.5`, row `gap-3`, actions `gap-2` |
| Sheet header | primitive `p-4`, plus `border-b border-[#e0e0e0] bg-[#f4f4f4]` |
| Audit list | `grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 px-4 font-mono text-xs` |

Primitive card padding is `--card-spacing: --spacing(4)` (16px), or `--spacing(3)` (12px) at `size="sm"`. Product cards set `gap-0 py-0` and apply the `px-4` scale above instead.

## Card

```tsx
<Card
  className={`gap-0 rounded-none border border-[#e0e0e0] bg-white py-0 shadow-none ring-0 transition-colors hover:border-[#8d8d8d] ${stripe}`}
>
  <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 rounded-none bg-[#f4f4f4]/60 px-4 py-3">
    {/* status badge, jurisdiction badge, meta */}
  </CardHeader>
  <Separator className="bg-[#e0e0e0]" />
  <CardContent className="space-y-4 p-4">
    <span className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
      Section label
    </span>
    <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 text-sm leading-relaxed text-[#161616]">
      Well content
    </div>
  </CardContent>
  <Separator className="bg-[#e0e0e0]" />
  <CardFooter className="flex flex-wrap items-center justify-between gap-3 rounded-none border-0 bg-[#f4f4f4]/40 px-4 py-2.5">
    <div className="font-mono text-xs text-[#525252]">ID: record-id</div>
    {/* reject + approve buttons */}
  </CardFooter>
</Card>
```

`stripe` is `border-l-4` plus the status color from the table above.

## Status badge

```tsx
<Badge
  variant="outline"
  className="h-auto rounded-none border-[#f1c21b] bg-[#fcf4d6] px-2 py-0.5 text-xs font-medium text-[#161616]"
>
  <WarningAltFilled className="mr-1.5 h-3.5 w-3.5 text-[#b28600]" />
  Pending Clinical Review
</Badge>
```

Swap the color classes and icon for `APPROVED` and `REJECTED` using the status table. Do not use the default pill `Badge` variant for review state.

## Button

Primary and danger actions are square Carbon buttons, `size="sm"` plus `h-8` and `text-xs font-medium`. Icons sit before the label.

```tsx
<Button
  variant="outline"
  size="sm"
  className="h-8 rounded-none border-[#da1e28] text-xs font-medium text-[#da1e28] hover:bg-[#da1e28] hover:text-white"
>
  <CloseFilled className="mr-1.5 h-3.5 w-3.5" />
  Reject
</Button>
<Button
  size="sm"
  className="h-8 rounded-none bg-[#0f62fe] text-xs font-medium text-white hover:bg-[#0353e9]"
>
  <CheckmarkFilled className="mr-1.5 h-3.5 w-3.5" />
  Approve Guidance
</Button>
```

Secondary text actions use `variant="ghost"` `size="sm"` with `h-7 rounded-none px-2 text-xs text-[#0f62fe] hover:bg-[#edf5ff] hover:text-[#0043ce]`. Inline text toggles can be a native `button` with `text-xs font-medium text-[#0f62fe] hover:underline` and a Carbon icon, as the source-language toggle does.

Disable the action that matches the current status (`disabled` when already approved or already rejected). Do not switch that button to a different color to show the disabled state; the primitive `disabled:opacity-50` treatment is enough.
