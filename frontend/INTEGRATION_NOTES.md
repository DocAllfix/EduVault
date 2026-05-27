# Frontend Integration Notes — shadcn-admin → Nexus EduVault

> Questo file è la **fonte di verità** sull'origine e sulla regola di evoluzione del frontend.
> Riferimenti: CLAUDE.md REI-1 (template = base, mai sostituire dalla tela bianca),
> REI-11 (qualità UI top-down con skill `impeccable`, `frontend-design`, `design-system`,
> `brand`, `ui-styling`), BLUEPRINT v7.0 §10 (cablaggio API/WebSocket).

## Origine

| Campo | Valore |
|---|---|
| Repo upstream | https://github.com/satnaing/shadcn-admin |
| Versione package.json | `2.2.1` |
| Commit clonato (HEAD) | `a6352e7df0de652e4349f6bf53ca246de6ff013f` |
| Data ultimo commit upstream | `2026-04-21T18:35:37+07:00` |
| Subject ultimo commit upstream | `refactor: replace classNames with suggested Tailwind canonical classes` |
| Data di clone in questo repo | `2026-05-24` |
| Operatore | Claude Code in sessione FASE 6.1 |

La cartella `frontend/.git` originale è stata **rimossa** subito dopo il clone:
il template diventa parte integrante di questo monorepo, non un submodule né un fork
manutenuto a parte. Da questo momento la sola fonte autoritativa del codice
frontend è il presente repository.

## Regola di evoluzione (REI-1)

> **Questo template è la BASE. Le modifiche avvengono per adattamento, non per sostituzione.**

In pratica:

- **NON cancellare** intere cartelle del template `frontend/src/components/ui/`,
  `frontend/src/components/layout/`, `frontend/src/features/`,
  `frontend/src/routes/`. Si modificano in-place o si aggiungono fratelli accanto.
- **NON rigenerare** componenti shadcn-ui che esistono già qui — usarli direttamente.
  Solo aggiungerne di nuovi via `npx shadcn@latest add <name>` quando manca il primitive.
- **NON inventare** un design da tela bianca. Per qualsiasi nuova pagina partire dalla
  pagina più simile del template e adattarla (es. dashboard analytics → courses list,
  tasks → jobs queue, users → utenti operatori/admin).
- **Branding C.F.P. Montessori** (logo + palette `#C82E6E` / `#769E2E`) si applica
  sovrascrivendo le variabili CSS `:root` in `src/index.css` e mappando token semantici
  `--brand-primary` / `--brand-secondary` in `tailwind.config.ts`. **Non** si edita ogni
  componente uno per uno.

## Reference upstream

Per consultare la versione "vergine" del template a fini di confronto o per riportare
backport di novità upstream:

- Repo: https://github.com/satnaing/shadcn-admin
- Commit di partenza nostro: `a6352e7df0de652e4349f6bf53ca246de6ff013f`
- Diff utile per capire cosa abbiamo personalizzato:
  `git diff <commit-upstream>..HEAD -- frontend/` (richiede `git remote add upstream` ad-hoc).

## Orphan template files esclusi da tsc (FASE 6.10)

Per il build production verde i seguenti file template sono esclusi da
`tsconfig.app.json` (rispettando REI-1: non li cancello, li ignoro):

- `src/features/auth/forgot-password/` — REI-4: BP §08 v1.0 non prevede reset
- `src/features/auth/otp/` — REI-4: no 2FA in v1.0
- `src/features/auth/sign-up/` — REI-4: solo admin crea utenti (no self-reg)
- `src/features/auth/sign-in/sign-in-2.tsx` — variante non usata (manteniamo `sign-in/index.tsx`)

Le **route** di questi file sono state rimosse in 6.10. I file restano
sul disco per facilitare backport upstream del template; quando FASE 7
includerà reset password ufficiale, si potrà ripescare lo scaffolding da
`forgot-password/` senza ricominciare da zero.

Anche le seguenti route legacy template non sono nella sidebar Cfp ma
RESTANO compilate e raggiungibili via URL diretto (solo URL — non c'è
link nella UI Cfp): `/apps`, `/chats`, `/users`, `/tasks`, `/settings/*`,
`/clerk/**`, `/help-center`, `/(errors)/*`, `/errors/$error`. Sono pagine
demo del template e saranno rimosse in FASE 7 (cleanup pre-deploy).

## Fatti scoperti durante il clone (rilevanti per 6.2)

1. **Package manager: `pnpm`, non npm.** Il template ha `pnpm-lock.yaml` e non
   `package-lock.json`. In 6.2 useremo `pnpm install` (più veloce, deterministico,
   compatibile con `package.json` esistente). Se preferiamo restare su `npm` lo
   decideremo in 6.2, ma servirà rigenerare il lockfile.

2. **`@clerk/react` è preinstallato** (`^6.4.2` in `dependencies`). Clerk è un sistema
   di auth managed che entra in conflitto con REI-4 (JWT custom + bcrypt, nessuna
   auth cloud). In 6.2 va **rimosso da `package.json`** e ogni route del template che
   lo importa va sostituita con il nostro `auth/AuthContext` cablato sui nostri endpoint
   `/api/auth/login` e `/api/auth/refresh`. Tracciato in `VERIFICATION_DEBT.md` come
   discrepanza al prossimo update.

3. **Tailwind v4 (`@tailwindcss/vite ^4.2.2`).** Il template usa la nuova sintassi
   Tailwind 4 con plugin Vite, NON la classica `tailwind.config.js` v3. La
   personalizzazione palette/token avverrà via direttive CSS `@theme` in `src/index.css`,
   non in un file `tailwind.config.ts` v3. Da considerare in 6.3 (branding).

## File correlati

- `c:/Users/user/EduVault/CLAUDE.md` — REI-1, REI-4, REI-11, REI-14
- `c:/Users/user/EduVault/docs/SKILLS_PLAYBOOK.md` — skill per FASE 6
- `c:/Users/user/EduVault/docs/SKILLS_PER_PHASE_CHEATSHEET.md`
- `c:/Users/user/EduVault/docs/HANDOFF_PHASE6.md`
- `c:/Users/user/EduVault/logo_03.jpg` — sorgente branding, varianti SVG/PNG da
  generare in 6.3 (tech-debt `#R7` in `VERIFICATION_DEBT.md`)

---

## Inventario Template shadcn-admin

> Snapshot read-only del template a commit `a6352e7`. Nessun file modificato.
> Aggiornato il 2026-05-24 da Claude Code (FASE 6.2).

### Struttura Directory

Albero `frontend/src/` (top-level):

```
src/
├── assets/           # logo template, brand-icons, custom icons (theme/sidebar)
├── components/
│   ├── ui/           # 30 primitives shadcn/ui
│   ├── layout/       # app-sidebar, header, top-nav, nav-user, team-switcher, main
│   ├── data-table/   # toolbar, pagination, bulk-actions, faceted-filter, column-header
│   ├── coming-soon, command-menu, config-drawer, confirm-dialog
│   ├── date-picker, learn-more, long-text, navigation-progress
│   ├── password-input, profile-dropdown, search, select-dropdown
│   ├── sign-out-dialog, skip-to-main, theme-switch
├── config/fonts.ts
├── context/          # direction-, font-, layout-, search-, theme-provider
├── features/         # business pages (apps, auth, chats, dashboard, errors, settings, tasks, users)
├── hooks/            # use-dialog-state, use-mobile, use-table-url-state
├── lib/              # cookies, handle-server-error, show-submitted-data, utils
├── routes/           # tanstack-router file-based (auth, errors, _authenticated, clerk)
├── stores/auth-store.ts  # Zustand auth store (TEMPLATE PLACEHOLDER, da riscrivere REI-4)
├── styles/           # index.css (Tailwind v4 entry) + theme.css (CSS variables OKLCH)
├── test-utils/, *.d.ts, main.tsx, routeTree.gen.ts, vite-env.d.ts
```

Output `find ... | sort` (estratto, 162 file totali). I 30 file `ui/*.tsx` sono i primitive shadcn — vedi tabella più sotto.

### Pagine Esistenti

| Path | Descrizione template | Riutilizzabile per Nexus? | Pagina Nexus target |
|---|---|---|---|
| `src/features/dashboard/index.tsx` | Dashboard analytics con 4 stat cards + tabs Overview/Analytics + grafici Recharts | **Sì → adattare** | Dashboard corsi (KPI: corsi attivi, in coda, completati, throughput; nessun Recharts in v1) |
| `src/features/tasks/index.tsx` | Tabella tasks con `TasksProvider`, `TasksTable`, `TasksPrimaryButtons`, `TasksDialogs` — modello completo CRUD con TanStack Table | **Sì → BASE per lista corsi** | Lista corsi (`/api/courses`): colonne titolo, modulo, status, progress%, data, owner, actions |
| `src/features/users/index.tsx` | Tabella utenti con search filter, bulk actions, invite dialog | **Sì → adattare** | Gestione operatori/admin (`/api/admin/...`, futura sezione) |
| `src/features/auth/sign-in/index.tsx` | Card centrata "Sign in" con `UserAuthForm`, link a sign-up, footer terms/privacy | **Sì → base login** | `/login` cablato su `POST /api/auth/login` (rimuovere sign-up: REI-4, no self-registration) |
| `src/features/auth/sign-in/sign-in-2.tsx` | Login layout 2-col con illustration | **Opzionale** | Versione branded con logo C.F.P. + claim "Formazione Globale" |
| `src/features/auth/forgot-password/index.tsx` | Form forgot password (richiede backend endpoint) | **Posticipato** | Non in BP §08; deferire a FASE 7 |
| `src/features/auth/otp/index.tsx` | OTP code form | **NO** | BP §08 non prevede 2FA — rimuovere |
| `src/features/auth/sign-up/index.tsx` | Sign-up form | **NO** | REI-4 + BP §08: solo admin crea utenti, no self-registration — rimuovere |
| `src/features/settings/*` (profile/account/appearance/display/notifications) | 5 sotto-pagine settings con sidebar interna | **Parziale** | Tenere `appearance` (theme switcher) e `profile` (cambio password). Rimuovere account/notifications/display (non in BP) |
| `src/features/apps/index.tsx` | Galleria app con icone brand (Discord, GitHub, Slack…) | **NO** | Out of scope Nexus — rimuovere route + features/apps |
| `src/features/chats/index.tsx` | Chat UI 2-pane | **NO** | Out of scope Nexus — rimuovere |
| `src/features/errors/{401,403,404,500,503}.tsx` | Pagine errore brandizzabili | **Sì → tenere** | Stesse route, ribrandizzate C.F.P. |
| `src/routes/clerk/**` (tutto) | Routes preconfigurate Clerk (sign-in/up/user-management) | **NO** | REI-4 vieta Clerk — eliminare cartella + dipendenza `@clerk/react` |

**Nuove pagine Nexus da creare ex-novo (parte da template più affine):**

| Pagina Nexus | Endpoint backend | Pagina template di partenza |
|---|---|---|
| Wizard "Genera corso" multi-step (form ingestione + opzioni) | `POST /api/courses` | nessuna diretta → costruire con `Stepper` (da aggiungere) + `Form` + `Tabs` |
| Detail corso con WebSocket progress + download | `GET /api/courses/{id}`, `WS /ws/jobs/{job_id}`, `GET /api/courses/{id}/download/*` | dashboard (KPI card stile) + tasks (lista artefatti) |
| Knowledge Base ingest (upload PDF + lista regolamenti) | `POST /api/regulations`, `GET /api/regulations` | tasks (tabella) + users (invite dialog → upload dialog) |
| Catalog / Brand presets (admin) | `GET /api/catalog`, `GET /api/brand-presets` | users (tabella read-only) |
| Admin metrics dashboard | `GET /api/admin/metrics`, `GET /api/dashboard/stats` | dashboard (4 KPI card) |

### Componenti shadcn/ui Disponibili

Tutti i 30 primitive presenti in `src/components/ui/`:

| File | Componente | Note Nexus |
|---|---|---|
| alert-dialog.tsx | AlertDialog | conferma azioni distruttive (DELETE corso) |
| alert.tsx | Alert | banner errori/warning |
| avatar.tsx | Avatar | profilo header |
| badge.tsx | Badge | **chiave** per status corso (running/completed/failed/cancelled) |
| button.tsx | Button | brand-primary applicato qui |
| calendar.tsx | Calendar | filtri date list corsi |
| card.tsx | Card | layout base ogni pagina |
| checkbox.tsx | Checkbox | bulk select tabelle |
| collapsible.tsx | Collapsible | nav-group sidebar |
| command.tsx | Command (cmdk) | command-menu Ctrl+K |
| dialog.tsx | Dialog | wizard step / form modali |
| dropdown-menu.tsx | DropdownMenu | profile dropdown, row actions |
| form.tsx | Form (react-hook-form + zod) | **chiave** per wizard generazione |
| input-otp.tsx | InputOTP | da rimuovere se rimuoviamo OTP page |
| input.tsx | Input | form fields |
| label.tsx | Label | form labels |
| popover.tsx | Popover | tooltip avanzati, search filter |
| radio-group.tsx | RadioGroup | scelta livello pubblico (entry-level / intermediate / advanced) wizard |
| scroll-area.tsx | ScrollArea | lista chunk normativi |
| select.tsx | Select | dropdown modulo/regolamento |
| separator.tsx | Separator | divider visivi |
| sheet.tsx | Sheet | side panel detail corso |
| sidebar.tsx | Sidebar (composito) | layout principale — già usato in `app-sidebar.tsx` |
| skeleton.tsx | Skeleton | loading state |
| sonner.tsx | Toaster (Sonner) | **chiave** notifiche success/error |
| switch.tsx | Switch | toggle preferenze |
| table.tsx | Table | base per lista corsi |
| tabs.tsx | Tabs | dashboard tabs Overview/Analytics |
| textarea.tsx | Textarea | speaker notes editor (futuro) |
| tooltip.tsx | Tooltip | help inline |

**Compositi NON-ui (riusabili):**
- `data-table/` — TanStack Table + toolbar + faceted-filter + pagination + bulk-actions + column-header + view-options → **base diretta** per lista corsi.
- `command-menu.tsx` — Ctrl+K palette: tenere, popolare con quick actions Nexus.
- `theme-switch.tsx` — light/dark/system toggle: tenere.
- `password-input.tsx` — input con eye toggle: usare nel login.
- `navigation-progress.tsx` — barra top route change: tenere.
- `config-drawer.tsx` — pannello config sidebar/layout/direction: utile per admin, mantenere.

### Layout e Navigazione

| Aspetto | Path | Note |
|---|---|---|
| **Sidebar component** | `src/components/layout/app-sidebar.tsx` | usa `Sidebar` shadcn primitive + `useLayout()` (variant + collapsible). Header sidebar mostra `<TeamSwitcher>` (placeholder commerciale, da sostituire con logo C.F.P. fisso o `<AppTitle>` già commentato nel codice). |
| **Sidebar data (nav items)** | `src/components/layout/data/sidebar-data.ts` | array `navGroups` (`General`, `Pages`, `Other`) — **da riscrivere in 6.4** con le 7 pagine Nexus reali. Include riferimento a `ClerkLogo` e voci `/clerk/**` da rimuovere REI-4. |
| **Header (top bar pagina)** | `src/components/layout/header.tsx` | sticky `h-16` con `SidebarTrigger` + slot children. Ogni pagina compone il proprio Header con `<Search>`, `<ThemeSwitch>`, `<ConfigDrawer>`, `<ProfileDropdown>`. |
| **Authenticated layout (shell)** | `src/components/layout/authenticated-layout.tsx` | `<SearchProvider><LayoutProvider><SidebarProvider><AppSidebar /><SidebarInset><Outlet /></SidebarInset></SidebarProvider></LayoutProvider></SearchProvider>` — applicato come component a `routes/_authenticated/route.tsx`. |
| **Main wrapper** | `src/components/layout/main.tsx` | container con padding/spacing standard per il body pagina. |
| **TopNav** (sub-nav orizzontale) | `src/components/layout/top-nav.tsx` | usato in dashboard per "Overview / Customers / Products / Settings"; utile per sotto-tab pagina corso. |
| **Route config** | TanStack Router **file-based** | entrypoint `src/main.tsx` → `createRouter({ routeTree })` con `routeTree.gen.ts` auto-generato (NON editare). Le route stanno in `src/routes/` con convenzioni: `(auth)/*` group senza shell, `_authenticated/*` con shell, `__root.tsx` root con `<NavigationProgress />`, `<Outlet />`, `<Toaster />`, devtools. |
| **Root route** | `src/routes/__root.tsx` | `createRootRouteWithContext<{ queryClient: QueryClient }>` — query client iniettato come router context. NotFound/Error component referenziati da `features/errors`. |
| **Authenticated route** | `src/routes/_authenticated/route.tsx` | guard layout `component: AuthenticatedLayout`. **Non c'è ancora un auth guard reale** — la verifica JWT andrà aggiunta qui in 6.5 con `beforeLoad` redirect a `/sign-in` se `useAuthStore.getState().auth.accessToken` vuoto. |
| **Auth store (Zustand)** | `src/stores/auth-store.ts` | placeholder template: `user: AuthUser \| null`, `accessToken: string`, persiste accessToken in cookie `thisisjustarandomstring`. **Da riscrivere in 6.5**: tipi `User` allineati a `app/models/core.py` (id UUID, email, role enum admin/operator), gestione refresh token, expiry check. |

### Sistema di Temi

| Aspetto | Dove | Note |
|---|---|---|
| **CSS variables** | `src/styles/theme.css` | Tutte le var token semantici in **OKLCH** (più moderno di HEX). Sezione `:root` (light) + sezione `.dark` (dark mode). Include token sidebar (`--sidebar`, `--sidebar-primary`, `--sidebar-border`, ecc.) **ereditati da `--background/--primary/--border`** — quindi cambiare il primary cambia automaticamente sidebar primary. |
| **Entry CSS** | `src/styles/index.css` | `@import 'tailwindcss'` (Tailwind v4, **no `tailwind.config.ts`**) + `@import 'tw-animate-css'` + `@import './theme.css'`. Definisce custom variant `@custom-variant dark (&:is(.dark *))` e utility `@utility container/no-scrollbar/faded-bottom`. **Tutta la personalizzazione di palette/font/spacing si fa qui o in theme.css con `@theme`.** |
| **Token attuali (light root)** | `theme.css` :root | `--background: oklch(1 0 0)` (bianco), `--foreground: oklch(0.129 0.042 264.695)` (quasi nero blu-ish), `--primary: oklch(0.208 0.042 265.755)` (blu scuro slate), `--border: oklch(0.929 0.013 255.508)` (grigio chiaro). Palette neutra slate — enterprise di default. |
| **Dark mode** | classe `.dark` su `<html>` | Applicata da `ThemeProvider` (`src/context/theme-provider.tsx`). Modi: `light` / `dark` / `system`. Persiste in cookie `vite-ui-theme` (1y). System mode usa `matchMedia('(prefers-color-scheme: dark)')`. `useTheme()` hook esposto. |
| **Implementazione branding C.F.P. (PIANO 6.3)** | `theme.css` | Sostituire `--primary` con `#C82E6E` convertito in OKLCH (~`oklch(0.578 0.181 7.5)`); aggiungere `--brand-secondary` ≈ `oklch(0.624 0.146 132)` per `#769E2E`. Nota: il sistema attuale **non ha** un `--secondary` brand color (il `--secondary` esistente è un grigio chiarissimo neutro per backgrounds, NON è semantico "secondary brand action"). Servirà aggiungere una nuova coppia `--brand-primary`/`--brand-secondary` e mappare componenti specifici (status badge, accent CTA) — non sovrascrivere `--secondary` template. |
| **Fonts** | `src/config/fonts.ts` + `src/context/font-provider.tsx` | Provider che applica font scelto a `<html>`. Pluri-font predisposti — in 6.3 forzeremo un singolo font enterprise (Inter o IBM Plex). |

### Stack tecnico effettivo (estratto da `package.json`)

- **Router**: `@tanstack/react-router ^1.168.22` (file-based, devtools)
- **Server state**: `@tanstack/react-query ^5.99.0` (+ devtools)
- **Table**: `@tanstack/react-table ^8.21.3`
- **Client state**: `zustand ^?` (vedi lockfile)
- **HTTP**: `axios ^1.15.0` → wrapper in `lib/handle-server-error.ts`
- **Forms**: `react-hook-form` + `zod` + `@hookform/resolvers`
- **Toast**: `sonner` via `Toaster` in root
- **Icons**: `lucide-react` (sidebar-data importa Construction, LayoutDashboard, Bug, ecc.)
- **Tailwind**: v4 via `@tailwindcss/vite ^4.2.2`
- **Auth managed**: `@clerk/react ^6.4.2` → **DA RIMUOVERE in 6.2/6.5** (REI-4)
- **Test**: `vitest` con browser mode (Playwright chromium)

### Implicazioni operative per 6.3+

1. **Auth**: il file `stores/auth-store.ts` esiste già con shape semplice — riscrivere in 6.5 con tipi del backend, NO clerk, JWT refresh logic. Eliminare `routes/clerk/**` interamente.
2. **WebSocket**: il template non ha alcun helper WS. In 6.5 creare `lib/ws-client.ts` con il contratto di `docs/POLLING_FALLBACK.md` (WS primario + polling REST 30s).
3. **API client**: il template usa `axios` ma non c'è ancora un wrapper Nexus-specific. In 6.5 creare `lib/api.ts` con base URL da `import.meta.env.VITE_API_URL`, interceptor auth, refresh token.
4. **Wizard "Genera corso"**: nessuno `Stepper` shadcn nel template — primitive da aggiungere via `npx shadcn@latest add stepper` o componente custom in 6.6.
5. **Forms con validazione**: `react-hook-form` + `zod` già nel package. In 6.6 definire schemi Zod allineati a `app/models/requests.py` (Pydantic backend).
6. **Status badge corsi**: usare `Badge` variant custom — definire varianti `running` (rosa brand), `completed` (verde brand), `failed` (destructive), `cancelled` (muted) in `components/ui/badge.tsx` esteso o nuova `<CourseStatusBadge>`.
