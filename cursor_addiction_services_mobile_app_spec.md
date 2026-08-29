# Cursor Build Specification — Israel Addiction Treatment Services Mobile Web App

## 1. Project Goal

Build a production-quality, mobile-first, Hebrew RTL web application that helps people in Israel find **public addiction-treatment services and private/nonprofit services that are supervised, licensed, funded, contracted, or otherwise officially recognized by the Ministry of Health and/or Ministry of Welfare**.

The app must be simple enough for a stressed person or family member to use quickly, but rich enough for professionals to filter and compare services.

The primary use case is:

> “I need help with an addiction problem. Show me the relevant treatment options near me, explain what each place actually does, and make it easy to call or contact them.”

The app must prioritize:
- clarity,
- trust,
- accessibility,
- fast decision-making,
- mobile usability,
- accurate source attribution,
- clear distinction between public and supervised external providers.

The application is **not** a clinical diagnostic tool and must not give medical diagnoses.

---

# 2. Product Principles

## 2.1 Human-first
The user may be:
- a person with an addiction,
- a parent,
- spouse,
- sibling,
- friend,
- social worker,
- health professional,
- municipal employee,
- case manager.

The UI must assume the user may be under stress.

Avoid:
- dense institutional language,
- bureaucratic jargon,
- excessive form fields,
- clinical terminology without explanation.

Prefer:
- short sentences,
- large touch targets,
- clear categories,
- immediate phone/contact actions,
- “what happens here?” explanations.

---

## 2.2 Mobile-first

The main experience must be designed first for:
- iPhone,
- Android mobile browsers,
- small screens,
- portrait orientation.

Desktop should be responsive and polished, but mobile is the primary design target.

---

## 2.3 Hebrew-first / RTL-first

Primary language:
- Hebrew

Direction:
- `dir="rtl"`

All layouts, icons, drawers, menus, chevrons, pagination, cards, filters, and search must behave correctly in RTL.

Optional:
- prepare the architecture for future English support,
- but do not build full i18n unless it is trivial.

---

# 3. Core User Flows

## Flow A — Find help quickly

1. User opens app.
2. Sees large search box:
   - “מה סוג העזרה שאתה מחפש?”
3. User chooses one of:
   - סמים
   - אלכוהול
   - תרופות / אופיואידים
   - הימורים
   - מין / פורנוגרפיה
   - מסכים / רשתות חברתיות / גיימינג
   - תחלואה כפולה
   - התמכרויות התנהגותיות
4. App asks optional:
   - אזור בארץ
   - גיל
   - ציבורי בלבד / כולל פרטי מפוקח
5. Results appear immediately.
6. User opens a service card.
7. User can:
   - call,
   - email,
   - navigate,
   - open source,
   - save to favorites,
   - share.

---

## Flow B — Search by location

1. User taps:
   - “מצא מענה באזור שלי”
2. User selects region manually or allows geolocation.
3. App shows services sorted by:
   - proximity if coordinates are available,
   - otherwise region/city relevance.
4. User can switch between:
   - cards,
   - map,
   - compact list.

---

## Flow C — Professional filtering

A social worker or professional should be able to filter by:
- addiction type,
- service type,
- region,
- city,
- age group,
- public vs supervised provider,
- inpatient vs outpatient,
- dual diagnosis,
- youth,
- women,
- men,
- family support,
- detox,
- rehabilitation,
- psychiatric support.

---

# 4. Main Navigation

Mobile bottom navigation:

1. **בית**
2. **חיפוש**
3. **מפה**
4. **שמורים**
5. **מידע**

Desktop:
- top navigation bar,
- persistent search/filter sidebar where useful.

---

# 5. Home Screen

The home screen must feel calm, trustworthy, and immediately useful.

## Hero

Title:

> למצוא את המענה המתאים להתמכרות

Subtitle:

> שירותים ציבוריים ומסגרות פרטיות מפוקחות בישראל, במקום אחד.

Primary CTA:

> מצא טיפול

Secondary CTA:

> חיפוש לפי אזור

---

## Quick category buttons

Large icon cards:

- סמים
- אלכוהול
- הימורים
- מין ופורנוגרפיה
- מסכים וגיימינג
- תרופות ואופיואידים
- תחלואה כפולה
- כל סוגי ההתמכרות

Each category must be one tap.

---

## Emergency / urgent help banner

Add a visible but non-alarming section:

> מצב חירום רפואי או סכנה מיידית?

Buttons:
- 101 מד״א
- 100 משטרה
- 118 משרד הרווחה
- 5400* משרד הבריאות

Do not present this as diagnosis.
Use neutral wording.

---

# 6. Search Screen

The search screen is the core of the product.

## Search field

Placeholder:

> חפש מוסד, עיר, סוג טיפול או התמכרות

Search must match:
- institution name,
- city,
- region,
- addiction,
- treatment type,
- operator,
- phone,
- notes.

Use client-side fuzzy matching.

Recommended:
- Fuse.js

---

# 7. Filters

Use a mobile filter drawer / bottom sheet.

Filters:

## Institution type
- הכל
- ציבורי
- פרטי / מלכ״ר מפוקח

## Operator
- משרד הבריאות
- משרד הרווחה
- רשות מקומית
- קופת חולים
- בית חולים ציבורי
- עמותה / מלכ״ר
- חברה פרטית

## Region
- ארצי
- חיפה והצפון
- תל אביב והמרכז
- ירושלים
- דרום

## Addiction
- סמים
- אלכוהול
- תרופות / אופיואידים
- הימורים
- מין / פורנוגרפיה
- מסכים / רשתות / גיימינג
- תחלואה כפולה
- התמכרויות התנהגותיות

## Treatment type
- גמילה רפואית
- אשפוזית
- טיפול אמבולטורי
- קהילה טיפולית
- טיפול פנימייתי
- מרכז יום
- פסיכיאטריה
- טיפול תרופתי
- טיפול פרטני / קבוצתי
- טיפול משפחתי
- שיקום בקהילה
- שיקום תעסוקתי
- הפחתת נזקים
- טיפול נוער

## Population
- מבוגרים
- נוער
- צעירים
- נשים
- גברים
- משפחות
- קהילת להט״ב
- תחלואה כפולה

---

# 8. Results Screen

Default result presentation:
- card list.

Each card must show only the most important information.

## Card layout

### Header
- institution name
- institution type badge

Badges:
- ציבורי
- פרטי מפוקח
- מלכ״ר מפוקח
- קופת חולים
- בית חולים

### Location
- city
- region

### Key service chips
Examples:
- גמילה רפואית
- אמבולטורי
- הימורים
- נוער
- תחלואה כפולה

Show max 4 chips.
Then:
> +3 נוספים

### Contact buttons

Primary:
- התקשר

Secondary:
- פרטים

Optional:
- ניווט
- שמור

---

# 9. Institution Detail Page

This page is crucial.

## Header

Institution name

Status badge:
- ציבורי
- פרטי / מלכ״ר מפוקח

Operator:
- who operates it

---

## Section: במה מטפלים כאן?

List addiction categories.

Use friendly wording.

---

## Section: איזה סוג טיפול ניתן?

Show service types.

Examples:
- גמילה רפואית
- טיפול אמבולטורי
- טיפול קבוצתי
- טיפול משפחתי
- קהילה טיפולית
- מרכז יום
- פסיכיאטריה
- שיקום

---

## Section: למי השירות מתאים?

Display:
- age,
- gender restrictions,
- youth/adults,
- family,
- dual diagnosis,
- LGBT if relevant.

---

## Section: איך פונים?

Show:
- phone,
- email,
- address,
- official website.

Buttons:
- התקשר עכשיו
- שלח אימייל
- פתח ניווט
- פתח אתר רשמי

---

## Section: מעמד ופיקוח

This must be highly visible.

Examples:

> שירות ציבורי של משרד הבריאות

or

> מסגרת חיצונית המופעלת בפיקוח / רישוי / התקשרות של משרד הרווחה

or

> מוסד פרטי המופיע במאגר אשפוזיות הגמילה של משרד הבריאות

Do not use vague labels.

---

## Section: מקור המידע

Show:
- source organization,
- source URL,
- last verification date.

Example:

> נבדק לאחרונה: 28.08.2026

Button:
> פתח מקור רשמי

---

# 10. Map View

Implement with:
- Leaflet + OpenStreetMap

Do not require a paid map provider.

Pins:
- public service: one icon style
- supervised private/nonprofit: second icon style

Do not rely on color alone.
Use icons + labels.

Tap marker:
- open compact institution preview card.

Map controls:
- current location
- zoom
- filter
- switch back to list

---

# 11. Favorites

Use browser localStorage.

Users can save institutions.

Screen:
> המענים ששמרתי

No account required.

Favorites should persist across sessions.

---

# 12. Share

Each institution page must support:

- native Web Share API when available,
- copy link fallback.

Share text example:

> מצאתי את המענה הזה במאגר שירותי ההתמכרויות:
> [Institution Name]

---

# 13. Data Model

Use a structured JSON dataset.

Recommended TypeScript interface:

```ts
export interface AddictionService {
  id: string;
  name: string;
  institutionType:
    | "public"
    | "supervised_nonprofit"
    | "supervised_private";

  operatorType:
    | "ministry_health"
    | "ministry_welfare"
    | "municipality"
    | "health_fund"
    | "public_hospital"
    | "nonprofit"
    | "private_company";

  operatorName?: string;

  region:
    | "national"
    | "north"
    | "center"
    | "jerusalem"
    | "south";

  city: string;

  address?: string;

  latitude?: number;
  longitude?: number;

  addictions: AddictionType[];
  services: ServiceType[];

  population?: string[];

  phone?: string[];
  email?: string[];
  website?: string;

  supervisionText: string;

  officialSources: SourceReference[];

  notes?: string;

  verifiedAt: string;
}

export interface SourceReference {
  label: string;
  url: string;
  sourceType:
    | "gov_il"
    | "data_gov_il"
    | "municipality"
    | "health_fund"
    | "hospital"
    | "provider";
}

export type AddictionType =
  | "drugs"
  | "alcohol"
  | "opioids"
  | "gambling"
  | "sex_porn"
  | "screens_social_gaming"
  | "dual_diagnosis"
  | "behavioral";

export type ServiceType =
  | "medical_detox"
  | "inpatient"
  | "outpatient"
  | "therapeutic_community"
  | "day_center"
  | "psychiatry"
  | "medication"
  | "individual_group"
  | "family"
  | "community_rehab"
  | "vocational_rehab"
  | "harm_reduction"
  | "youth"
  | "assessment"
  | "referral";
```

---

# 14. Seed Data

Use the existing curated dataset from the previous research task.

Create:

```text
src/data/addiction-services.json
```

The dataset must preserve:
- institution name,
- public/supervised status,
- operator,
- region,
- city,
- addiction categories,
- treatment types,
- target population,
- contact details,
- address,
- supervision status,
- source URL,
- verification date.

Do not silently alter or normalize values in a way that changes meaning.

---

# 15. Data Quality Rules

Every institution must have:
- name,
- type,
- region,
- city or service area,
- at least one addiction type,
- at least one service type,
- supervision/public-status explanation,
- at least one source,
- verification date.

Do not publish fabricated phone numbers.

If no phone exists:
show:

> לא נמצא מספר טלפון מאומת

If data is incomplete:
show a visible warning.

---

# 16. Reliability / Trust UX

The app must visually distinguish information quality.

Each record should show:

### Verified
> מקור רשמי זמין

### Needs re-check
> מומלץ לוודא טלפונית לפני פנייה

Do not use scary red warning styles unless necessary.

---

# 17. Design Language

Design goals:
- calm,
- modern,
- trustworthy,
- not hospital-like,
- not childish,
- not corporate IBM-like.

Use:
- large whitespace,
- rounded cards,
- clear typography,
- minimal shadows,
- subtle hierarchy.

Recommended:
- Tailwind CSS
- shadcn/ui

Hebrew fonts:
- Assistant
- Heebo
- Rubik

Prefer:
- `Assistant` or `Heebo`.

---

# 18. Color System

Do not use aggressive colors.

Suggested semantic palette:

- Primary: blue
- Public: blue
- Supervised external: green
- Warning: amber
- Emergency: red
- Neutral background: very light gray

Important:
- never use color as the only semantic indicator,
- always include icon/text.

---

# 19. Accessibility

Target WCAG 2.2 AA.

Requirements:
- keyboard navigable
- visible focus state
- screen-reader labels
- semantic HTML
- proper button labels
- min tap target 44x44 px
- sufficient contrast
- support browser text zoom
- no critical information only in icons
- RTL screen-reader-friendly ordering

---

# 20. Technical Stack

Preferred:

```text
Next.js 15+
React
TypeScript
Tailwind CSS
shadcn/ui
Lucide icons
Fuse.js
Leaflet
OpenStreetMap
Zod
Vitest
Playwright
```

Alternative:
- Vite + React is acceptable if Cursor determines it is cleaner.

Do not over-engineer.

No backend is required for v1.

---

# 21. Application Structure

Recommended:

```text
src/
  app/
    page.tsx
    search/
      page.tsx
    map/
      page.tsx
    service/
      [id]/
        page.tsx
    favorites/
      page.tsx
    about/
      page.tsx

  components/
    SearchBar.tsx
    FilterDrawer.tsx
    ServiceCard.tsx
    ServiceBadge.tsx
    AddictionChip.tsx
    ServiceChip.tsx
    ContactActions.tsx
    SourcePanel.tsx
    EmergencyBanner.tsx
    MobileBottomNav.tsx
    MapView.tsx
    EmptyState.tsx
    DataWarning.tsx

  data/
    addiction-services.json

  lib/
    search.ts
    filters.ts
    favorites.ts
    geo.ts
    formatting.ts
    validation.ts

  types/
    addiction.ts

  tests/
```

---

# 22. Search Logic

Search across:

```text
name
city
region
addictions
services
operator
population
notes
```

Search should:
- tolerate partial Hebrew words,
- ignore punctuation,
- normalize common Hebrew punctuation,
- rank exact institution matches highest.

Examples:

`הימורים`
must return institutions with gambling support.

`חיפה`
must return all relevant services in Haifa.

`מין`
must return services explicitly supporting sexual addiction.

---

# 23. Sorting

Allow sorting by:
- relevance,
- institution name,
- city,
- region,
- public first,
- closest to me.

Default:
- relevance if searching,
- otherwise name.

---

# 24. Location / Geolocation

Do not require geolocation.

If user chooses:
> השתמש במיקום שלי

Ask browser permission.

If denied:
- gracefully fall back to manual region selection.

Do not store exact location.

---

# 25. Privacy

No login.
No tracking of addiction searches.
No analytics in v1 unless explicitly enabled later.

Do not send:
- search query,
- addiction type,
- geolocation,
- favorites

to third-party analytics.

If analytics are later added:
- anonymize,
- document,
- require explicit privacy review.

---

# 26. Safety Disclaimer

Display discreetly:

> המידע באתר נועד לסייע באיתור שירותים ואינו מחליף אבחון או ייעוץ רפואי. במצב חירום או סכנה מיידית יש לפנות לשירותי החירום.

Do not repeat this everywhere.

Best locations:
- About page
- footer
- emergency panel

---

# 27. Empty States

Example:

> לא מצאנו מענה שמתאים לכל המסננים שבחרת.

Buttons:
- נקה מסנן אחד
- הצג את כל המענים באזור
- הצג גם מסגרות פרטיות מפוקחות

Do not show a blank page.

---

# 28. Contact Actions

Mobile:
- phone → `tel:`
- email → `mailto:`
- address → maps route
- website → new tab

Each action must be large and obvious.

Primary CTA should generally be:
> התקשר

---

# 29. Source Transparency

Every institution must show:
- official source,
- direct source URL,
- verified date.

Never hide the source behind a generic “more info”.

Use a dedicated section:

## מקור ופיקוח

Example:

> מקור: משרד הבריאות  
> נבדק: 28.08.2026  
> [פתח מקור רשמי]

---

# 30. Public vs Supervised Provider UX

This distinction is central.

Use exact terminology.

## Public

Label:

> ציבורי

Description:

> שירות שמופעל ישירות על ידי משרד ממשלתי, רשות מקומית, קופת חולים או בית חולים ציבורי.

## Supervised nonprofit/private

Label:

> פרטי / מלכ״ר מפוקח

Description:

> מסגרת שאינה שירות ממשלתי ישיר אך מופיעה כמורשית, מפוקחת, מתקשרת או מופעלת במיקור חוץ על ידי גוף ממשלתי.

Never call supervised private providers “government services”.

---

# 31. Cost Information

If the dataset does not contain verified cost data:
do not invent it.

Show:

> עלות: יש לברר מול המסגרת

Optional future field:

```ts
paymentType:
  | "public"
  | "health_fund"
  | "subsidized"
  | "private"
  | "unknown";
```

---

# 32. PWA

Make the application installable.

Implement:
- web manifest
- app icons
- theme color
- standalone mode
- basic offline caching for static UI and dataset

Offline mode should still allow:
- browsing previously loaded service data,
- favorites.

Do not imply contact numbers were revalidated offline.

---

# 33. Responsive Behavior

## Mobile
- bottom navigation
- filter bottom-sheet
- 1-column cards
- sticky search

## Tablet
- 2-column cards
- optional side filter

## Desktop
- side filters
- list/map split view
- larger detail layouts

---

# 34. Performance

Targets:
- Lighthouse Performance > 90
- Accessibility > 95
- Best Practices > 95
- SEO > 90

Avoid:
- giant JS bundles
- unnecessary animation
- loading map libraries on pages without maps

Lazy-load Leaflet.

---

# 35. SEO

Pages should be indexable.

Metadata examples:

```text
טיפול בהתמכרויות בישראל
גמילה מאלכוהול בישראל
טיפול בהימורים בישראל
מרכזי גמילה מפוקחים בישראל
```

Institution detail pages:
- institution name
- city
- treatment type

Add structured data where appropriate.

---

# 36. Testing

## Unit tests

Test:
- filters
- search
- sorting
- public/private distinction
- favorite storage
- data validation

## Integration tests

Test:
- filter combination
- search → details
- favorite → favorites page
- call button link
- source link

## Playwright

Mobile viewport:

```text
390 x 844
```

Test:
1. open home
2. choose gambling
3. select center region
4. show supervised private providers
5. open institution
6. save favorite
7. return to favorites
8. verify saved institution

---

# 37. Data Validation

Use Zod.

Build should fail if:
- record has no name,
- no type,
- no region,
- no addiction,
- no service,
- no supervision text,
- no source,
- invalid URL,
- invalid verifiedAt date.

---

# 38. Admin / Maintenance Architecture

Do not build an admin panel in v1.

But prepare for future dataset updates.

Keep data isolated from UI.

Add:

```text
scripts/validate-data.ts
```

Optional:

```text
scripts/import-csv.ts
```

This will allow future updates from government datasets.

---

# 39. Future Update Capability

Design so future versions can:
- fetch Ministry of Health datasets,
- fetch Ministry of Welfare datasets,
- compare records,
- flag changed phone/address/status,
- show “last checked”.

Do not implement automatic scraping in v1.

---

# 40. Suggested Homepage Copy

Hero:

> למצוא טיפול בהתמכרות — בצורה פשוטה וברורה

Subtitle:

> חיפוש בשירותים ציבוריים ובמסגרות פרטיות מפוקחות בישראל לפי סוג התמכרות, אזור וסוג טיפול.

CTA:

> מצא מענה

Secondary:

> הצג את כל השירותים

---

# 41. Suggested UX Microcopy

Filter title:

> סינון תוצאות

Institution type:

> מי מפעיל את השירות?

Location:

> איפה תרצה לקבל טיפול?

Treatment type:

> איזה סוג מענה מתאים לך?

No result:

> לא מצאנו התאמה מלאה

Source:

> מאיפה המידע?

Verification:

> נבדק לאחרונה

Favorite:

> שמור

Share:

> שתף

---

# 42. Do Not

Do not:
- diagnose addiction,
- score severity,
- recommend one institution as medically “best” without evidence,
- hide private/public distinction,
- fabricate contact details,
- scrape personal user information,
- require sign-up,
- use dark patterns,
- overload the first screen,
- use complex clinical terminology as primary labels,
- make every screen look like a government portal,
- present the app as an emergency medical service.

---

# 43. Definition of Done

The project is complete only when:

- Hebrew RTL works correctly
- Mobile UX is polished
- Public vs supervised external providers are clearly separated
- Search works
- Filters work
- Sorting works
- Institution pages work
- Phone/email/navigation actions work
- Map works
- Favorites work
- Share works
- Source links work
- Verification date is displayed
- PWA works
- Accessibility checks pass
- Dataset validation passes
- Playwright mobile test passes
- No TypeScript errors
- No console errors
- README is complete

---

# 44. README Requirements

README must contain:

## Purpose
What the app does.

## Data policy
How institutions are included.

## Public vs supervised definition
Clear explanation.

## Data source
Government and official sources.

## Run locally

```bash
npm install
npm run dev
```

## Validate data

```bash
npm run validate:data
```

## Test

```bash
npm test
npm run test:e2e
```

## Build

```bash
npm run build
```

---

# 45. Cursor Execution Instructions

Cursor must execute this work as an engineering project, not just generate mock HTML.

## Phase 1 — Inspect

1. Inspect repository.
2. Identify framework.
3. Reuse existing components only if useful.
4. Do not destroy unrelated code.

## Phase 2 — Architecture

Create:
- types
- dataset
- search/filter logic
- route structure
- shared UI components

## Phase 3 — Core UX

Implement:
1. home
2. search
3. filters
4. result cards
5. institution details

## Phase 4 — Advanced UX

Implement:
1. map
2. favorites
3. share
4. PWA

## Phase 5 — Quality

Run:
- TypeScript
- lint
- unit tests
- Playwright
- production build

Fix all failures.

---

# 46. Cursor Working Style

Do not ask for approval after every file.

Instead:

1. inspect,
2. plan briefly,
3. implement,
4. test,
5. report.

If something is ambiguous:
- choose the safest simple implementation,
- document the decision.

Do not leave placeholders such as:
- TODO
- Lorem ipsum
- fake phone numbers
- fake addresses
- mock institutional data

unless explicitly marked as demo-only.

---

# 47. UX Acceptance Scenarios

## Scenario 1 — Parent looking for gambling treatment

Input:
- התמכרות: הימורים
- אזור: מרכז

Expected:
- public municipal services
- supervised Mila centers
- relevant inpatient or outpatient options
- clear contact actions

---

## Scenario 2 — Young adult with substance use + psychiatric condition

Input:
- תחלואה כפולה
- אזור: צפון

Expected:
- dual diagnosis services
- appropriate supervised therapeutic communities
- clear warning that suitability must be clinically assessed

---

## Scenario 3 — Sexual / pornography addiction

Input:
- מין / פורנוגרפיה

Expected:
- only institutions explicitly documented as supporting that category
- do not infer treatment capability

---

## Scenario 4 — Social media / gaming addiction

Input:
- מסכים / רשתות / גיימינג

Expected:
- institutions explicitly offering behavioral addiction / gaming support
- no unrelated substance detox facilities

---

# 48. Final Product Standard

The result should feel like:

- a trusted national service directory,
- designed by a professional UX team,
- usable by a person in distress,
- transparent about data and supervision,
- fast on mobile,
- simple enough to understand in under 30 seconds.

The design should not feel like:
- a spreadsheet,
- a government database,
- a generic admin dashboard,
- a marketing site,
- a clinical hospital portal.

The user should quickly answer three questions:

1. **מי יכול לעזור לי?**
2. **איזה סוג טיפול הם נותנים?**
3. **איך אני יוצר קשר עכשיו?**

---

# 49. Initial Data Import

Use the curated addiction services dataset generated in the previous research step as the initial source.

If an HTML or JSON dataset already exists in the repository, parse and normalize it into:

```text
src/data/addiction-services.json
```

Preserve the original source URLs and verification dates.

Do not delete the source file until the normalized dataset has been validated.

---

# 50. Final Cursor Deliverable

At completion, provide:

```text
1. Working application
2. README.md
3. src/data/addiction-services.json
4. scripts/validate-data.ts
5. unit tests
6. Playwright tests
7. PWA manifest
8. clean production build
```

Also provide a concise implementation report:

```text
Implemented
Changed
Tested
Known limitations
Recommended next steps
```

The implementation report must specifically state:
- number of institutions loaded,
- number of public services,
- number of supervised external services,
- number of regions covered,
- whether all source URLs pass validation.

---

# 51. Recommended Product Name

Working name:

> **מענה — טיפול בהתמכרויות בישראל**

Alternative names:
- מענה להתמכרויות
- מוצאים טיפול
- דרך לטיפול
- מרכז המענים להתמכרויות

Use “מענה” as the default unless the repository already has a product name.
