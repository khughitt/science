# Natural-Systems Prose Epistemics Application Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the shipped science P2/P3/P4 prose-epistemics framework to a small natural-systems Markdown pilot and expose the resulting P4 coverage ramp in `npm run health`.

**Architecture:** Keep Python as the epistemic source of truth: natural-systems generates or stores P2 input artifacts, invokes the shipped science CLI for ingest, promotion, grounding, and P4 health, then reads only `data/prose-health/prose-health.json` from TypeScript. The pilot is intentionally small, Markdown-only, and read-only on the TS side; evidence authoring follows from the first unbacked backlog rather than being hidden inside the health reader.

**Tech Stack:** TypeScript/tsx/Vitest in `~/d/natural-systems`; shipped `uv run science annotate ...` CLI from `~/d/science`; JSON artifacts under `data/prose-health`, `data/prose-decomposition-inputs`, `data/prose-decompositions`, and `data/prose-grounding`.

---

## Pilot Limitation

This plan deliberately hand-authors the first decomposition artifacts in a deterministic
writer. That validates the P2/P3/P4 plumbing, promotion state, grounding reports, and
natural-systems health integration; it does not validate the offline agent's decomposition
quality. Treat a green pilot as "the pipe works for reviewed artifacts," not as proof that
candidate/skip classification is reliable.

After this pilot lands, run one genuine offline-agent decomposition artifact for one pilot
source through the same ingest/check/promote/ground/health loop and compare its candidate
and skip rows against the reviewed fixture.

## Implementation Notes

Run implementation in an isolated worktree for `~/d/natural-systems` before editing:

```bash
cd ~/d/natural-systems
git status --short
git worktree add ../natural-systems-prose-epistemics -b prose-epistemics-pilot
cd ../natural-systems-prose-epistemics
```

Use the repo's canonical graph command:

```bash
npm run kg:build
```

Do not run retired `knowledge/scripts/*` graph builders or edit `knowledge/graph.trig` directly.

## File Structure

Create or modify these files in `~/d/natural-systems`:

- Create: `data/prose-health/manifest.json`
  - P4 manifest and denominator authority for the pilot.
- Create: `scripts/prose-epistemics/config.ts`
  - Pilot source list and pinned grounding floor.
- Create: `scripts/prose-epistemics/write-pilot-decompositions.ts`
  - Deterministic starter P2 decomposition artifact writer for the pilot.
- Create: `scripts/prose-epistemics/build-pilot-health.ts`
  - Repeatable wrapper for graph build, P3 grounding, and P4 health using the pinned floor.
- Create: `scripts/prose-epistemics/__tests__/config.test.ts`
- Create: `scripts/prose-epistemics/__tests__/write-pilot-decompositions.test.ts`
- Create: `scripts/health/proseEpistemics.ts`
  - Read-only P4 artifact loader/formatter for TypeScript consumers.
- Create: `scripts/health/checkers/proseEpistemics.ts`
  - Health checker that surfaces missing/invalid/stale P4 state as findings.
- Create: `scripts/health/__tests__/proseEpistemics.test.ts`
- Create: `scripts/health/__tests__/checkers/proseEpistemics.test.ts`
- Modify: `scripts/health/types.ts`
  - Add P4 prose epistemics types and `HealthContext.proseEpistemics`.
- Modify: `scripts/health/context.ts`
  - Load `data/prose-health/prose-health.json` when the checker or dashboard needs it.
- Modify: `scripts/health/checkers/index.ts`
  - Register `proseEpistemicsChecker`.
- Modify: `scripts/health/scorer.ts`
  - Add `prose-epistemics` to `UNSCORED_CHECKERS` with an explicit comment.
- Modify: `scripts/health/bundle.ts`
  - Carry prose epistemics into the health bundle result.
- Modify: `scripts/health/reporter.ts`
  - Render a short P4 summary in the text report.
- Modify: `scripts/health/index.ts`
  - Include prose epistemics in the JSON report.
- Modify: `scripts/health/__tests__/integration.test.ts`
  - Assert the JSON report carries the prose epistemics section.
- Modify: `package.json`
  - Add operator scripts for the pilot.

Generated pilot artifacts are expected after running tasks:

- `data/prose-decomposition-inputs/pilot/*.json`
- `data/prose-decompositions/<slug>/...`
- `data/prose-grounding/<slug>/grounding.json`
- `data/prose-health/prose-health.json`
- `entities/prose-sources/*.md`
- promoted proposition files under the science entity home selected by the framework

Generated artifacts are committed in this pilot on purpose so review can inspect the
first real P2/P3/P4 payloads. Expect `knowledge/graph.trig` and JSON artifact churn in
these commits; a later campaign can switch to reproducible build outputs once the consumer
contract is stable against real content.

---

### Task 1: Pilot Manifest And Configuration

**Files:**
- Create: `data/prose-health/manifest.json`
- Create: `scripts/prose-epistemics/config.ts`
- Test: `scripts/prose-epistemics/__tests__/config.test.ts`
- Modify: `package.json`

- [ ] **Step 1: Write the failing config test**

Create `scripts/prose-epistemics/__tests__/config.test.ts`:

```ts
import { describe, expect, it } from 'vitest';

import { GROUNDING_FLOOR, PILOT_SOURCES } from '../config.ts';

describe('prose epistemics pilot config', () => {
  it('pins the supported grounding floor explicitly', () => {
    expect(GROUNDING_FLOOR).toBe('supported');
  });

  it('declares three Markdown pilot sources with prose-source refs', () => {
    expect(PILOT_SOURCES).toEqual([
      {
        slug: 'cole-hopf-morphism-analysis',
        sourceRef: 'prose-source:cole-hopf-morphism-analysis',
        path: 'entities/discussions/0020-cole-hopf-morphism-analysis.md',
        title: 'Cole-Hopf Transform: Morphism Type Analysis',
      },
      {
        slug: 'tropical-dequantization-functor-backbone',
        sourceRef: 'prose-source:tropical-dequantization-functor-backbone',
        path: 'entities/questions/0114-tropical-dequantization-as-functor-backbone.md',
        title: 'Tropical Dequantization As Functor Backbone',
      },
      {
        slug: 'universality-classes-two-faces',
        sourceRef: 'prose-source:universality-classes-two-faces',
        path: 'entities/discussions/0075-representing-universality-classes-two-faces.md',
        title: 'Representing Universality Classes: Two Faces',
      },
    ]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
npx vitest scripts/prose-epistemics/__tests__/config.test.ts
```

Expected: FAIL because `scripts/prose-epistemics/config.ts` does not exist.

- [ ] **Step 3: Add the pilot config**

Create `scripts/prose-epistemics/config.ts`:

```ts
export const GROUNDING_FLOOR = 'supported' as const;

export interface PilotSource {
  slug: string;
  sourceRef: `prose-source:${string}`;
  path: string;
  title: string;
}

export const PILOT_SOURCES: PilotSource[] = [
  {
    slug: 'cole-hopf-morphism-analysis',
    sourceRef: 'prose-source:cole-hopf-morphism-analysis',
    path: 'entities/discussions/0020-cole-hopf-morphism-analysis.md',
    title: 'Cole-Hopf Transform: Morphism Type Analysis',
  },
  {
    slug: 'tropical-dequantization-functor-backbone',
    sourceRef: 'prose-source:tropical-dequantization-functor-backbone',
    path: 'entities/questions/0114-tropical-dequantization-as-functor-backbone.md',
    title: 'Tropical Dequantization As Functor Backbone',
  },
  {
    slug: 'universality-classes-two-faces',
    sourceRef: 'prose-source:universality-classes-two-faces',
    path: 'entities/discussions/0075-representing-universality-classes-two-faces.md',
    title: 'Representing Universality Classes: Two Faces',
  },
];
```

- [ ] **Step 4: Add the P4 pilot manifest**

Create `data/prose-health/manifest.json`:

```json
{
  "schema_version": 1,
  "sources": [
    {
      "source_ref": "prose-source:cole-hopf-morphism-analysis",
      "path": "entities/discussions/0020-cole-hopf-morphism-analysis.md",
      "title": "Cole-Hopf Transform: Morphism Type Analysis"
    },
    {
      "source_ref": "prose-source:tropical-dequantization-functor-backbone",
      "path": "entities/questions/0114-tropical-dequantization-as-functor-backbone.md",
      "title": "Tropical Dequantization As Functor Backbone"
    },
    {
      "source_ref": "prose-source:universality-classes-two-faces",
      "path": "entities/discussions/0075-representing-universality-classes-two-faces.md",
      "title": "Representing Universality Classes: Two Faces"
    }
  ]
}
```

- [ ] **Step 5: Add package scripts for the pilot commands**

Modify `package.json` and add these entries under `"scripts"`:

```json
{
  "prose:write-pilot-decompositions": "tsx scripts/prose-epistemics/write-pilot-decompositions.ts",
  "prose:build-pilot-health": "tsx scripts/prose-epistemics/build-pilot-health.ts"
}
```

Keep the existing scripts unchanged.

- [ ] **Step 6: Run test to verify it passes**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
npx vitest scripts/prose-epistemics/__tests__/config.test.ts
```

Expected: PASS.

- [ ] **Step 7: Verify the manifest loads through shipped P4**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
uv run science annotate build-prose-health --root . --format json
```

Expected: command succeeds and prints JSON with `summary.declared_sources` equal to `3`. It may include `missing_decomposition` findings because P2 artifacts have not been ingested yet.

- [ ] **Step 8: Commit**

```bash
git add package.json data/prose-health/manifest.json scripts/prose-epistemics/config.ts scripts/prose-epistemics/__tests__/config.test.ts
git commit -m "feat: declare prose epistemics pilot manifest"
```

---

### Task 2: Deterministic Pilot Decomposition Writer

**Files:**
- Create: `scripts/prose-epistemics/write-pilot-decompositions.ts`
- Test: `scripts/prose-epistemics/__tests__/write-pilot-decompositions.test.ts`

- [ ] **Step 1: Write the failing decomposition-writer tests**

Create `scripts/prose-epistemics/__tests__/write-pilot-decompositions.test.ts`:

```ts
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { describe, expect, it } from 'vitest';

import {
  buildPilotDecompositionPayload,
  pilotArtifactPath,
} from '../write-pilot-decompositions.ts';
import { PILOT_SOURCES } from '../config.ts';

describe('write-pilot-decompositions', () => {
  it('builds a valid P2-shaped payload with current source hash and reviewed units', () => {
    const root = mkdtempSync(join(tmpdir(), 'ns-prose-'));
    const source = PILOT_SOURCES[0];
    const sourcePath = join(root, source.path);
    mkdirSync(dirname(sourcePath), { recursive: true });
    writeFileSync(
      sourcePath,
      [
        '# Cole-Hopf Transform: Morphism Type Analysis',
        '',
        '## Current Position',
        '',
        '### What exists in the model graph',
        '',
        'The guide has 5 morphism types: **specialization**, **limit**, **composition**, **duality**, **analogy**. The Hamiltonian link follows.',
        '',
        '## Focus',
        '',
        'Does the Cole-Hopf (exponential) transformation warrant a new morphism type, or does the existing vocabulary accommodate it?',
        '',
      ].join('\n'),
      { encoding: 'utf-8' },
    );

    const payload = buildPilotDecompositionPayload(root, source);

    expect(payload.schema_version).toBe(1);
    expect(payload.source).toMatchObject({
      kind: 'prose-source',
      slug: 'cole-hopf-morphism-analysis',
      path: source.path,
      title: source.title,
    });
    expect(payload.source.content_hash).toMatch(/^sha256:[a-f0-9]{64}$/);
    expect(payload.artifact.id).toBe('pilot-2026-06-19');
    expect(payload.units).toHaveLength(2);
    expect(payload.units[0]).toMatchObject({
      unit_id: 'u001',
      disposition: 'candidate',
      locator: {
        regime: 'markdown-heading-path',
        value: [
          'Cole-Hopf Transform: Morphism Type Analysis',
          'Current Position',
          'What exists in the model graph',
        ],
      },
      payload: {
        type: 'proposition',
        stance: 'asserted',
        exact: 'The guide has 5 morphism types: **specialization**, **limit**, **composition**, **duality**, **analogy**.',
      },
    });
    expect(payload.units[1]).toMatchObject({
      unit_id: 'u002',
      disposition: 'skip',
      reason: { code: 'not_a_claim' },
    });
  });

  it('writes staged artifacts under data/prose-decomposition-inputs/pilot', () => {
    expect(pilotArtifactPath('/repo', PILOT_SOURCES[1])).toBe(
      '/repo/data/prose-decomposition-inputs/pilot/tropical-dequantization-functor-backbone.json',
    );
  });

  it('fails early if a reviewed quote is absent from the source text', () => {
    const root = mkdtempSync(join(tmpdir(), 'ns-prose-missing-'));
    const source = PILOT_SOURCES[0];
    mkdirSync(dirname(join(root, source.path)), { recursive: true });
    writeFileSync(
      join(root, source.path),
      [
        '# Cole-Hopf Transform: Morphism Type Analysis',
        '',
        '## Current Position',
        '',
        '### What exists in the model graph',
        '',
        'No reviewed quote here.',
        '',
        '## Focus',
        '',
        'Does the Cole-Hopf (exponential) transformation warrant a new morphism type, or does the existing vocabulary accommodate it? What edges are missing from the model graph?',
        '',
      ].join('\n'),
      { encoding: 'utf-8' },
    );

    expect(() => buildPilotDecompositionPayload(root, source)).toThrow(
      'reviewed quote is absent from entities/discussions/0020-cole-hopf-morphism-analysis.md',
    );
  });

  it('fails early if a reviewed heading path is absent from the source text', () => {
    const root = mkdtempSync(join(tmpdir(), 'ns-prose-heading-'));
    const source = PILOT_SOURCES[0];
    mkdirSync(dirname(join(root, source.path)), { recursive: true });
    writeFileSync(
      join(root, source.path),
      [
        '# Cole-Hopf Transform: Morphism Type Analysis',
        '',
        '## Current Position',
        '',
        'The guide has 5 morphism types: **specialization**, **limit**, **composition**, **duality**, **analogy**. The Hamiltonian link follows.',
        '',
      ].join('\n'),
      { encoding: 'utf-8' },
    );

    expect(() => buildPilotDecompositionPayload(root, source)).toThrow(
      'reviewed heading path is absent from entities/discussions/0020-cole-hopf-morphism-analysis.md',
    );
  });

  it('fails early if reviewed prefix and suffix context do not surround the quote', () => {
    const root = mkdtempSync(join(tmpdir(), 'ns-prose-context-'));
    const source = PILOT_SOURCES[0];
    mkdirSync(dirname(join(root, source.path)), { recursive: true });
    writeFileSync(
      join(root, source.path),
      [
        '# Cole-Hopf Transform: Morphism Type Analysis',
        '',
        '## Current Position',
        '',
        '### What exists in the model graph',
        '',
        'The guide has 5 morphism types: **specialization**, **limit**, **composition**, **duality**, **analogy**. Different suffix follows.',
        '',
        '## Focus',
        '',
        'Does the Cole-Hopf (exponential) transformation warrant a new morphism type, or does the existing vocabulary accommodate it? What edges are missing from the model graph?',
        '',
      ].join('\n'),
      { encoding: 'utf-8' },
    );

    expect(() => buildPilotDecompositionPayload(root, source)).toThrow(
      'reviewed quote context matched 0 times in section for entities/discussions/0020-cole-hopf-morphism-analysis.md',
    );
  });

  it('fails early if a reviewed quote appears only outside the matched section', () => {
    const root = mkdtempSync(join(tmpdir(), 'ns-prose-wrong-section-'));
    const source = PILOT_SOURCES[0];
    mkdirSync(dirname(join(root, source.path)), { recursive: true });
    writeFileSync(
      join(root, source.path),
      [
        '# Cole-Hopf Transform: Morphism Type Analysis',
        '',
        '## Current Position',
        '',
        '### What exists in the model graph',
        '',
        'This section has the right heading path but not the reviewed quote.',
        '',
        '### Different section',
        '',
        'The guide has 5 morphism types: **specialization**, **limit**, **composition**, **duality**, **analogy**. The Hamiltonian link follows.',
        '',
        '## Focus',
        '',
        'Does the Cole-Hopf (exponential) transformation warrant a new morphism type, or does the existing vocabulary accommodate it? What edges are missing from the model graph?',
        '',
      ].join('\n'),
      { encoding: 'utf-8' },
    );

    expect(() => buildPilotDecompositionPayload(root, source)).toThrow(
      'reviewed quote context matched 0 times in section for entities/discussions/0020-cole-hopf-morphism-analysis.md',
    );
  });

  it('fails early if reviewed quote context is non-unique within the matched section', () => {
    const root = mkdtempSync(join(tmpdir(), 'ns-prose-ambiguous-'));
    const source = PILOT_SOURCES[0];
    mkdirSync(dirname(join(root, source.path)), { recursive: true });
    writeFileSync(
      join(root, source.path),
      [
        '# Cole-Hopf Transform: Morphism Type Analysis',
        '',
        '## Current Position',
        '',
        '### What exists in the model graph',
        '',
        'The guide has 5 morphism types: **specialization**, **limit**, **composition**, **duality**, **analogy**. The Hamiltonian link follows.',
        '',
        'The guide has 5 morphism types: **specialization**, **limit**, **composition**, **duality**, **analogy**. The Hamiltonian link follows again.',
        '',
        '## Focus',
        '',
        'Does the Cole-Hopf (exponential) transformation warrant a new morphism type, or does the existing vocabulary accommodate it? What edges are missing from the model graph?',
        '',
      ].join('\n'),
      { encoding: 'utf-8' },
    );

    expect(() => buildPilotDecompositionPayload(root, source)).toThrow(
      'reviewed quote context matched 2 times in section for entities/discussions/0020-cole-hopf-morphism-analysis.md',
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
npx vitest scripts/prose-epistemics/__tests__/write-pilot-decompositions.test.ts
```

Expected: FAIL because `write-pilot-decompositions.ts` does not exist.

- [ ] **Step 3: Add the decomposition writer**

Create `scripts/prose-epistemics/write-pilot-decompositions.ts`:

The writer's pre-flight must mirror `resolve_markdown_locator`: match heading paths by
normalized suffix, search raw `prefix + exact + suffix` only inside matched section bodies,
and require exactly one context match.

```ts
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { PILOT_SOURCES, type PilotSource } from './config.ts';

const REPO_ROOT = resolve(import.meta.dirname, '../..');
const GENERATED_AT = '2026-06-19T00:00:00Z';
const ARTIFACT_ID = 'pilot-2026-06-19';
const PRODUCER = 'natural-systems-prose-epistemics-pilot';

interface CandidateUnit {
  unit_id: string;
  disposition: 'candidate';
  locator: {
    regime: 'markdown-heading-path';
    value: string[];
  };
  payload: {
    type: 'proposition';
    exact: string;
    prefix: string;
    suffix: string;
    stance: 'asserted';
    subject?: string;
    object?: string;
  };
}

interface SkipUnit {
  unit_id: string;
  disposition: 'skip';
  locator: {
    regime: 'markdown-heading-path-with-quote';
    value: string[];
    quote: {
      exact: string;
      prefix: string;
      suffix: string;
    };
  };
  reason: {
    code:
      | 'meta_commentary'
      | 'not_a_claim'
      | 'duplicate_or_restatement'
      | 'citation_or_reference_only'
      | 'out_of_scope'
      | 'unresolved_or_malformed';
    detail: string;
  };
}

type PilotUnit = CandidateUnit | SkipUnit;

export interface PilotDecompositionPayload {
  schema_version: 1;
  source: {
    kind: 'prose-source';
    slug: string;
    path: string;
    title: string;
    content_hash: string;
  };
  artifact: {
    id: string;
    generated_at: string;
    producer: string;
  };
  units: PilotUnit[];
}

const PILOT_UNITS: Record<string, PilotUnit[]> = {
  'cole-hopf-morphism-analysis': [
    {
      unit_id: 'u001',
      disposition: 'candidate',
      locator: {
        regime: 'markdown-heading-path',
        value: [
          'Cole-Hopf Transform: Morphism Type Analysis',
          'Current Position',
          'What exists in the model graph',
        ],
      },
      payload: {
        type: 'proposition',
        exact: 'The guide has 5 morphism types: **specialization**, **limit**, **composition**, **duality**, **analogy**.',
        prefix: '',
        suffix: ' The Hamiltonian',
        stance: 'asserted',
        subject: 'guide morphism vocabulary',
        object: 'five morphism types',
      },
    },
    {
      unit_id: 'u002',
      disposition: 'skip',
      locator: {
        regime: 'markdown-heading-path-with-quote',
        value: ['Cole-Hopf Transform: Morphism Type Analysis', 'Focus'],
        quote: {
          exact: 'Does the Cole-Hopf (exponential) transformation warrant a new morphism type, or does the existing vocabulary accommodate it?',
          prefix: '',
          suffix: ' What edges are missing',
        },
      },
      reason: {
        code: 'not_a_claim',
        detail: 'Framing question for the discussion, not an asserted domain claim.',
      },
    },
  ],
  'tropical-dequantization-functor-backbone': [
    {
      unit_id: 'u001',
      disposition: 'candidate',
      locator: {
        regime: 'markdown-heading-path',
        value: [
          'Is Z to log Z an idempotent (min-plus) dequantization, giving the free-energy functor its categorical backbone?',
          'Summary',
        ],
      },
      payload: {
        type: 'proposition',
        exact: 'This is the algebraic engine already implicit in the discussion\'s zero-noise limits — Léonard\'s Schrödinger → Monge–Kantorovich and Nutz–Wiesel\'s softmax-potentials → Kantorovich-potentials.',
        prefix: 'log∑exp` becomes a hard `min`.\n',
        suffix: '\nThe question:',
        stance: 'asserted',
        subject: 'idempotent dequantization',
        object: 'zero-noise limits',
      },
    },
    {
      unit_id: 'u002',
      disposition: 'skip',
      locator: {
        regime: 'markdown-heading-path-with-quote',
        value: [
          'Is Z to log Z an idempotent (min-plus) dequantization, giving the free-energy functor its categorical backbone?',
          'Why It Matters',
        ],
        quote: {
          exact: 'It would give `question:0112` concrete categorical structure',
          prefix: '',
          suffix: ': the functor\'s',
        },
      },
      reason: {
        code: 'meta_commentary',
        detail: 'Project-planning rationale about another question entity.',
      },
    },
  ],
  'universality-classes-two-faces': [
    {
      unit_id: 'u001',
      disposition: 'candidate',
      locator: {
        regime: 'markdown-heading-path',
        value: [
          'Representing universality classes — the two faces, discoverability, and catalog coverage',
          'Critical Analysis',
          'The two faces',
        ],
      },
      payload: {
        type: 'proposition',
        exact: 'KPZ has the cleanest invariant signature in the whole catalog (χ=1/3, ξ=2/3, z=3/2,\nTracy–Widom) yet has **no `profile:kpz-universality` record**.',
        prefix: 'worked\nexample created it** — Ising/DP got face 1, KPZ got face 2 — with no bridge between them.\n',
        suffix: '',
        stance: 'asserted',
        subject: 'KPZ',
        object: 'profile:kpz-universality gap',
      },
    },
    {
      unit_id: 'u002',
      disposition: 'skip',
      locator: {
        regime: 'markdown-heading-path-with-quote',
        value: [
          'Representing universality classes — the two faces, discoverability, and catalog coverage',
          'Focus',
        ],
        quote: {
          exact: 'This note (a) names the two faces and the redundancy/gap between them',
          prefix: '',
          suffix: ', (b)\nanswers',
        },
      },
      reason: {
        code: 'meta_commentary',
        detail: 'Statement about the purpose of the note rather than a domain claim.',
      },
    },
  ],
};

interface QuoteContext {
  exact: string;
  prefix: string;
  suffix: string;
}

interface MarkdownSection {
  level: number;
  title: string;
  headingPath: string[];
  bodyStart: number;
  bodyEnd: number;
}

export function pilotArtifactPath(root: string, source: PilotSource): string {
  return join(root, 'data/prose-decomposition-inputs/pilot', `${source.slug}.json`);
}

export function buildPilotDecompositionPayload(root: string, source: PilotSource): PilotDecompositionPayload {
  const sourcePath = join(root, source.path);
  const sourceText = readFileSync(sourcePath, 'utf-8');
  const units = PILOT_UNITS[source.slug];
  if (!units) {
    throw new Error(`No pilot units configured for ${source.sourceRef}`);
  }

  for (const unit of units) {
    const sectionBodies = sectionBodiesForHeadingPath(sourceText, source.path, unit.locator.value);
    const quote = quoteContext(unit);
    assertQuoteContextInSection(sourceText, source.path, sectionBodies, quote);
  }

  return {
    schema_version: 1,
    source: {
      kind: 'prose-source',
      slug: source.slug,
      path: source.path,
      title: source.title,
      content_hash: `sha256:${createHash('sha256').update(readFileSync(sourcePath)).digest('hex')}`,
    },
    artifact: {
      id: ARTIFACT_ID,
      generated_at: GENERATED_AT,
      producer: PRODUCER,
    },
    units,
  };
}

function quoteContext(unit: PilotUnit): QuoteContext {
  if (unit.disposition === 'candidate') {
    return {
      exact: unit.payload.exact,
      prefix: unit.payload.prefix,
      suffix: unit.payload.suffix,
    };
  }
  return unit.locator.quote;
}

function assertQuoteContextInSection(
  sourceText: string,
  sourcePath: string,
  sectionBodies: string[],
  quote: QuoteContext,
): void {
  if (!sourceText.includes(quote.exact)) {
    throw new Error(`reviewed quote is absent from ${sourcePath}: ${quote.exact}`);
  }
  const context = `${quote.prefix}${quote.exact}${quote.suffix}`;
  const matchCount = sectionBodies.reduce((count, body) => count + countOccurrences(body, context), 0);
  if (matchCount !== 1) {
    throw new Error(`reviewed quote context matched ${matchCount} times in section for ${sourcePath}: ${quote.exact}`);
  }
}

function countOccurrences(body: string, needle: string): number {
  let count = 0;
  let start = body.indexOf(needle);
  while (start !== -1) {
    count += 1;
    start = body.indexOf(needle, start + 1);
  }
  return count;
}

function sectionBodiesForHeadingPath(sourceText: string, sourcePath: string, headingPath: string[]): string[] {
  const sections = parseMarkdownSections(sourceText);
  const wanted = normalizeHeadingPath(headingPath);
  const matched = sections.filter((section) => headingPathMatches(section.headingPath, wanted));
  if (matched.length === 0) {
    throw new Error(`reviewed heading path is absent from ${sourcePath}: ${headingPath.join(' > ')}`);
  }
  return matched.map((section) => sourceText.slice(section.bodyStart, section.bodyEnd));
}

function headingPathMatches(activeHeadingPath: string[], wanted: string[]): boolean {
  if (wanted.length > activeHeadingPath.length) return false;
  const normalizedActive = normalizeHeadingPath(activeHeadingPath);
  return wanted.every((part, index) => part === normalizedActive[normalizedActive.length - wanted.length + index]);
}

function parseMarkdownSections(sourceText: string): MarkdownSection[] {
  const sections: MarkdownSection[] = [];
  const active: MarkdownSection[] = [];
  let offset = 0;
  const lines = sourceText.match(/[^\n]*\n|[^\n]+$/g) ?? [];
  for (const line of lines) {
    const match = /^(#{1,6})(?:\s+|$)(.*?)\s*$/.exec(line.replace(/\r?\n$/, ''));
    if (match) {
      const level = match[1].length;
      const title = match[2].replace(/\s+#+\s*$/, '').trim();
      while (active.length > 0 && active[active.length - 1].level >= level) {
        active.pop()!.bodyEnd = offset;
      }
      const section: MarkdownSection = {
        level,
        title,
        headingPath: [...active.map((item) => item.title), title],
        bodyStart: offset + line.length,
        bodyEnd: sourceText.length,
      };
      sections.push(section);
      active.push(section);
    }
    offset += line.length;
  }
  for (const section of active) {
    section.bodyEnd = sourceText.length;
  }
  return sections;
}

function normalizeHeadingPath(headingPath: string[]): string[] {
  return headingPath.map((part) => part.trim().toLocaleLowerCase().replace(/\s+/g, ' '));
}

export function writePilotDecompositionArtifacts(root = REPO_ROOT): string[] {
  const written: string[] = [];
  for (const source of PILOT_SOURCES) {
    const payload = buildPilotDecompositionPayload(root, source);
    const destination = pilotArtifactPath(root, source);
    mkdirSync(dirname(destination), { recursive: true });
    writeFileSync(destination, `${JSON.stringify(payload, null, 2)}\n`, 'utf-8');
    written.push(destination);
  }
  return written;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  for (const destination of writePilotDecompositionArtifacts()) {
    console.log(`wrote ${destination}`);
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
npx vitest scripts/prose-epistemics/__tests__/write-pilot-decompositions.test.ts
```

Expected: PASS.

- [ ] **Step 5: Generate the pilot decomposition input artifacts**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
npm run prose:write-pilot-decompositions
```

Expected: three files are written:

```text
data/prose-decomposition-inputs/pilot/cole-hopf-morphism-analysis.json
data/prose-decomposition-inputs/pilot/tropical-dequantization-functor-backbone.json
data/prose-decomposition-inputs/pilot/universality-classes-two-faces.json
```

- [ ] **Step 6: Validate each staged artifact through P2 ingest dry path**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
uv run science annotate ingest-prose-decomposition data/prose-decomposition-inputs/pilot/cole-hopf-morphism-analysis.json --root . --format json
uv run science annotate ingest-prose-decomposition data/prose-decomposition-inputs/pilot/tropical-dequantization-functor-backbone.json --root . --format json
uv run science annotate ingest-prose-decomposition data/prose-decomposition-inputs/pilot/universality-classes-two-faces.json --root . --format json
```

Expected: all three commands succeed and print JSON containing each `source_ref`. They will also persist P2 generations and prose-source entities; that is expected.

- [ ] **Step 7: Commit**

```bash
git add scripts/prose-epistemics/write-pilot-decompositions.ts scripts/prose-epistemics/__tests__/write-pilot-decompositions.test.ts data/prose-decomposition-inputs/pilot data/prose-decompositions entities/prose-sources
git commit -m "feat: stage pilot prose decompositions"
```

---

### Task 3: Check P2 Locators And Promote Reviewed Candidate Units

**Files:**
- Generated/modified by commands: `data/prose-decompositions/**`
- Generated/modified by commands: `entities/propositions/**`
- Generated/modified by commands: source entity files under `entities/prose-sources/**`

- [ ] **Step 1: Check each latest decomposition**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
uv run science annotate check-prose-decomposition --root . --source prose-source:cole-hopf-morphism-analysis --format json
uv run science annotate check-prose-decomposition --root . --source prose-source:tropical-dequantization-functor-backbone --format json
uv run science annotate check-prose-decomposition --root . --source prose-source:universality-classes-two-faces --format json
```

Expected: each command prints `units` where both pilot units have `"locator_status": "resolved"` and `"stale": false`.

If any unit reports `"locator_status": "unresolved"` or `"ambiguous"`, do not continue to
promotion. Correct that source's hardcoded `locator.value`, `payload.exact`,
`payload.prefix`, `payload.suffix`, or skip `locator.quote` in
`scripts/prose-epistemics/write-pilot-decompositions.ts`, rerun
`npm run prose:write-pilot-decompositions`, re-ingest that artifact, and rerun this check
until all pilot locators resolve.

- [ ] **Step 2: Dry-run promotion for the three reviewed candidate units**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
uv run science annotate promote-prose-decomposition --root . --source prose-source:cole-hopf-morphism-analysis --unit u001 --format json
uv run science annotate promote-prose-decomposition --root . --source prose-source:tropical-dequantization-functor-backbone --unit u001 --format json
uv run science annotate promote-prose-decomposition --root . --source prose-source:universality-classes-two-faces --unit u001 --format json
```

Expected: each command reports one planned promotion through `minted` or `linked`, and no `skipped` count for the selected unit.

If a dry-run returns a non-zero `skipped` count, inspect the JSON reason before applying.
An ambiguous existing proposition match is a legitimate promotion decision point: either
adjust the candidate wording so `decide_all` links cleanly, accept the intended existing
proposition by resolving the ambiguity in the graph/content, or leave the unit unpromoted
and record it as backlog. Do not force a duplicate mint to make this step green.

- [ ] **Step 3: Apply promotion one unit at a time**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
uv run science annotate promote-prose-decomposition --root . --source prose-source:cole-hopf-morphism-analysis --unit u001 --apply --format json
uv run science annotate promote-prose-decomposition --root . --source prose-source:tropical-dequantization-functor-backbone --unit u001 --apply --format json
uv run science annotate promote-prose-decomposition --root . --source prose-source:universality-classes-two-faces --unit u001 --apply --format json
```

Expected: each command reports exactly one applied promotion through `minted` or `linked`. A link to an existing proposition is acceptable if title normalization finds one; do not force a duplicate mint.

If the apply step skips after the dry-run was clean, stop and compare the new output to
the dry-run output. Promotion state or the entity corpus changed between the two commands;
rerun the dry-run and make the same disambiguation decision before applying again.

- [ ] **Step 4: Confirm promotion links are recorded by fingerprint**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
uv run science annotate check-prose-decomposition --root . --source prose-source:cole-hopf-morphism-analysis --format json
uv run science annotate check-prose-decomposition --root . --source prose-source:tropical-dequantization-functor-backbone --format json
uv run science annotate check-prose-decomposition --root . --source prose-source:universality-classes-two-faces --format json
```

Expected: each `u001` row has a non-null `promoted_to`, each `u002` row has `promoted_to: null`, and all rows remain resolved.

- [ ] **Step 5: Build and validate the graph**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
npm run kg:build
npm run kg:validate
```

Expected: both commands succeed. If materialization fails on a `prose-source:` ref, inspect the generated prose-source entity and rerun the failed promotion only after the source entity resolves.

- [ ] **Step 6: Commit**

```bash
git add data/prose-decompositions entities/prose-sources entities/propositions knowledge/graph.trig knowledge/sources
git commit -m "feat: promote pilot prose claims"
```

---

### Task 4: Repeatable Grounding And P4 Build Wrapper

**Files:**
- Create: `scripts/prose-epistemics/build-pilot-health.ts`
- Generated/modified by command: `data/prose-grounding/**`
- Generated/modified by command: `data/prose-health/prose-health.json`

- [ ] **Step 1: Write the failing wrapper smoke test**

Create `scripts/prose-epistemics/__tests__/build-pilot-health.test.ts`:

```ts
import { describe, expect, it } from 'vitest';

import { buildPilotHealthCommands } from '../build-pilot-health.ts';

describe('build-pilot-health', () => {
  it('pins the graph build, grounding floor, and P4 build commands', () => {
    expect(buildPilotHealthCommands()).toEqual([
      ['npm', 'run', 'kg:build'],
      [
        'uv',
        'run',
        'science',
        'annotate',
        'ground-prose-decomposition',
        '--root',
        '.',
        '--source',
        'prose-source:cole-hopf-morphism-analysis',
        '--floor',
        'supported',
        '--write',
      ],
      [
        'uv',
        'run',
        'science',
        'annotate',
        'ground-prose-decomposition',
        '--root',
        '.',
        '--source',
        'prose-source:tropical-dequantization-functor-backbone',
        '--floor',
        'supported',
        '--write',
      ],
      [
        'uv',
        'run',
        'science',
        'annotate',
        'ground-prose-decomposition',
        '--root',
        '.',
        '--source',
        'prose-source:universality-classes-two-faces',
        '--floor',
        'supported',
        '--write',
      ],
      ['uv', 'run', 'science', 'annotate', 'build-prose-health', '--root', '.', '--write'],
    ]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
npx vitest scripts/prose-epistemics/__tests__/build-pilot-health.test.ts
```

Expected: FAIL because `build-pilot-health.ts` does not exist.

- [ ] **Step 3: Add the wrapper**

Create `scripts/prose-epistemics/build-pilot-health.ts`:

```ts
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { GROUNDING_FLOOR, PILOT_SOURCES } from './config.ts';

export type Command = string[];

export function buildPilotHealthCommands(): Command[] {
  return [
    ['npm', 'run', 'kg:build'],
    ...PILOT_SOURCES.map((source) => [
      'uv',
      'run',
      'science',
      'annotate',
      'ground-prose-decomposition',
      '--root',
      '.',
      '--source',
      source.sourceRef,
      '--floor',
      GROUNDING_FLOOR,
      '--write',
    ]),
    ['uv', 'run', 'science', 'annotate', 'build-prose-health', '--root', '.', '--write'],
  ];
}

export function runCommands(commands: Command[]): void {
  for (const command of commands) {
    const [bin, ...args] = command;
    console.log(`$ ${command.join(' ')}`);
    const result = spawnSync(bin, args, { stdio: 'inherit' });
    if (result.status !== 0) {
      throw new Error(`command failed with status ${result.status}: ${command.join(' ')}`);
    }
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  runCommands(buildPilotHealthCommands());
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
npx vitest scripts/prose-epistemics/__tests__/build-pilot-health.test.ts
```

Expected: PASS.

- [ ] **Step 5: Build P3 grounding reports and P4 health**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
npm run prose:build-pilot-health
```

Expected: graph build succeeds, three grounding reports are written under `data/prose-grounding/<slug>/grounding.json`, and P4 writes `data/prose-health/prose-health.json`.

- [ ] **Step 6: Verify shipped science health reads P4**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
uv run science health --format json
```

Expected: JSON includes a `prose_epistemics` section with `applicable: true`, `summary.declared_sources: 3`, and `summary.current_candidate_units: 3`.

- [ ] **Step 7: Commit**

```bash
git add scripts/prose-epistemics/build-pilot-health.ts scripts/prose-epistemics/__tests__/build-pilot-health.test.ts data/prose-grounding data/prose-health/prose-health.json knowledge/graph.trig knowledge/sources
git commit -m "feat: build pilot prose grounding health"
```

---

### Task 5: Read-Only P4 Loader For Natural-Systems Health

**Files:**
- Create: `scripts/health/proseEpistemics.ts`
- Test: `scripts/health/__tests__/proseEpistemics.test.ts`
- Modify: `scripts/health/types.ts`

- [ ] **Step 1: Write the failing loader tests**

Create `scripts/health/__tests__/proseEpistemics.test.ts`:

```ts
import { mkdirSync, writeFileSync } from 'node:fs';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import {
  formatProseEpistemicsSummary,
  loadProseEpistemics,
} from '../proseEpistemics.ts';

function tempRoot(): string {
  return mkdtempSync(join(tmpdir(), 'ns-prose-epistemics-'));
}

describe('prose epistemics P4 loader', () => {
  it('is not applicable when neither manifest nor artifact exists', () => {
    expect(loadProseEpistemics(tempRoot())).toEqual({
      applicable: false,
      status: 'absent',
      findings: [],
    });
  });

  it('reports missing artifact when the manifest exists', () => {
    const root = tempRoot();
    mkdirSync(join(root, 'data/prose-health'), { recursive: true });
    writeFileSync(join(root, 'data/prose-health/manifest.json'), '{"schema_version":1,"sources":[]}\n');

    const result = loadProseEpistemics(root);

    expect(result).toMatchObject({
      applicable: true,
      status: 'missing_artifact',
      findings: [
        {
          code: 'PROSE_EPISTEMICS_ARTIFACT_MISSING',
          severity: 'P2',
          path: 'data/prose-health/prose-health.json',
        },
      ],
    });
  });

  it('loads summary, coverage, and artifact findings from P4 JSON', () => {
    const root = tempRoot();
    mkdirSync(join(root, 'data/prose-health'), { recursive: true });
    writeFileSync(join(root, 'data/prose-health/manifest.json'), '{"schema_version":1,"sources":[]}\n');
    writeFileSync(
      join(root, 'data/prose-health/prose-health.json'),
      JSON.stringify({
        schema_version: 1,
        generated_at: '2026-06-19T00:00:00Z',
        summary: {
          declared_sources: 3,
          current_candidate_units: 3,
          promoted_units: 3,
          grounded_units: 0,
          below_floor_units: 0,
          unbacked_units: 3,
          unpromoted_units: 0,
          skipped_units: 3,
          stale_units: 0,
          contested_units: 0,
        },
        coverage: {
          promotion: { numerator: 3, denominator: 3, ratio: 1 },
          grounding: { numerator: 0, denominator: 3, ratio: 0 },
          strict_grounding: { numerator: 0, denominator: 3, ratio: 0 },
        },
        sources: [],
        units: [],
        findings: [
          {
            code: 'missing_grounding',
            severity: 'warning',
            counts_as_issue: true,
            source_ref: 'prose-source:x',
            path: 'docs/x.md',
            message: 'missing grounding report',
          },
        ],
      }, null, 2),
    );

    const result = loadProseEpistemics(root);

    expect(result.status).toBe('present');
    expect(result.summary?.declared_sources).toBe(3);
    expect(result.findings).toHaveLength(1);
    expect(formatProseEpistemicsSummary(result)).toBe(
      'Prose epistemics: sources=3 candidates=3 promoted=3 grounded=0 unbacked=3 strict=0.0% findings=1',
    );
  });

  it('reports invalid JSON as an explicit finding', () => {
    const root = tempRoot();
    mkdirSync(join(root, 'data/prose-health'), { recursive: true });
    writeFileSync(join(root, 'data/prose-health/prose-health.json'), '{bad');

    const result = loadProseEpistemics(root);

    expect(result.status).toBe('invalid_artifact');
    expect(result.findings[0].code).toBe('PROSE_EPISTEMICS_ARTIFACT_INVALID');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
npx vitest scripts/health/__tests__/proseEpistemics.test.ts
```

Expected: FAIL because `scripts/health/proseEpistemics.ts` does not exist.

- [ ] **Step 3: Add P4 prose epistemics types**

Modify `scripts/health/types.ts` and add these interfaces near the existing prose health types:

```ts
export type ProseEpistemicsStatus =
  | 'absent'
  | 'missing_artifact'
  | 'invalid_artifact'
  | 'present';

export interface ProseEpistemicsFinding {
  code: string;
  severity: string;
  counts_as_issue?: boolean;
  source_ref?: string | null;
  path?: string;
  message: string;
}

export interface ProseEpistemicsSummary {
  declared_sources: number;
  sources_with_decomposition?: number;
  sources_with_grounding?: number;
  current_candidate_units: number;
  promoted_units: number;
  grounded_units: number;
  below_floor_units: number;
  unbacked_units: number;
  unpromoted_units: number;
  skipped_units: number;
  stale_units: number;
  contested_units: number;
}

export interface ProseEpistemicsMetric {
  numerator: number;
  denominator: number;
  ratio: number | null;
}

export interface ProseEpistemicsCoverage {
  promotion: ProseEpistemicsMetric;
  grounding: ProseEpistemicsMetric;
  strict_grounding: ProseEpistemicsMetric;
}

export interface ProseEpistemicsState {
  applicable: boolean;
  status: ProseEpistemicsStatus;
  summary?: ProseEpistemicsSummary;
  coverage?: ProseEpistemicsCoverage;
  findings: ProseEpistemicsFinding[];
}
```

Then add this optional field to `HealthContext`:

```ts
  proseEpistemics?: ProseEpistemicsState;
```

- [ ] **Step 4: Add the P4 loader**

Create `scripts/health/proseEpistemics.ts`:

```ts
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import type {
  ProseEpistemicsCoverage,
  ProseEpistemicsFinding,
  ProseEpistemicsState,
  ProseEpistemicsSummary,
} from './types.ts';

const MANIFEST_REL = 'data/prose-health/manifest.json';
const ARTIFACT_REL = 'data/prose-health/prose-health.json';

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function requiredNumber(row: Record<string, unknown>, key: keyof ProseEpistemicsSummary): number {
  const value = row[key];
  if (typeof value !== 'number') {
    throw new Error(`prose epistemics summary.${String(key)} must be a number`);
  }
  return value;
}

function parseSummary(value: unknown): ProseEpistemicsSummary {
  if (!isObject(value)) {
    throw new Error('prose epistemics summary must be an object');
  }
  return {
    declared_sources: requiredNumber(value, 'declared_sources'),
    sources_with_decomposition: typeof value.sources_with_decomposition === 'number'
      ? value.sources_with_decomposition
      : undefined,
    sources_with_grounding: typeof value.sources_with_grounding === 'number'
      ? value.sources_with_grounding
      : undefined,
    current_candidate_units: requiredNumber(value, 'current_candidate_units'),
    promoted_units: requiredNumber(value, 'promoted_units'),
    grounded_units: requiredNumber(value, 'grounded_units'),
    below_floor_units: requiredNumber(value, 'below_floor_units'),
    unbacked_units: requiredNumber(value, 'unbacked_units'),
    unpromoted_units: requiredNumber(value, 'unpromoted_units'),
    skipped_units: requiredNumber(value, 'skipped_units'),
    stale_units: requiredNumber(value, 'stale_units'),
    contested_units: requiredNumber(value, 'contested_units'),
  };
}

function parseMetric(value: unknown, label: string) {
  if (!isObject(value)) throw new Error(`prose epistemics coverage.${label} must be an object`);
  if (typeof value.numerator !== 'number') throw new Error(`prose epistemics coverage.${label}.numerator must be a number`);
  if (typeof value.denominator !== 'number') throw new Error(`prose epistemics coverage.${label}.denominator must be a number`);
  if (typeof value.ratio !== 'number' && value.ratio !== null) throw new Error(`prose epistemics coverage.${label}.ratio must be a number or null`);
  return {
    numerator: value.numerator,
    denominator: value.denominator,
    ratio: value.ratio,
  };
}

function parseCoverage(value: unknown): ProseEpistemicsCoverage {
  if (!isObject(value)) throw new Error('prose epistemics coverage must be an object');
  return {
    promotion: parseMetric(value.promotion, 'promotion'),
    grounding: parseMetric(value.grounding, 'grounding'),
    strict_grounding: parseMetric(value.strict_grounding, 'strict_grounding'),
  };
}

function parseFindings(value: unknown): ProseEpistemicsFinding[] {
  if (!Array.isArray(value)) throw new Error('prose epistemics findings must be an array');
  return value.map((item, index) => {
    if (!isObject(item)) throw new Error(`prose epistemics findings[${index}] must be an object`);
    const code = item.code;
    const severity = item.severity;
    const message = item.message;
    if (typeof code !== 'string') throw new Error(`prose epistemics findings[${index}].code must be a string`);
    if (typeof severity !== 'string') throw new Error(`prose epistemics findings[${index}].severity must be a string`);
    if (typeof message !== 'string') throw new Error(`prose epistemics findings[${index}].message must be a string`);
    return {
      code,
      severity,
      counts_as_issue: typeof item.counts_as_issue === 'boolean' ? item.counts_as_issue : undefined,
      source_ref: typeof item.source_ref === 'string' || item.source_ref === null ? item.source_ref : undefined,
      path: typeof item.path === 'string' ? item.path : undefined,
      message,
    };
  });
}

export function loadProseEpistemics(repoRoot: string): ProseEpistemicsState {
  const manifestPath = join(repoRoot, MANIFEST_REL);
  const artifactPath = join(repoRoot, ARTIFACT_REL);
  const hasManifest = existsSync(manifestPath);
  const hasArtifact = existsSync(artifactPath);

  if (!hasManifest && !hasArtifact) {
    return { applicable: false, status: 'absent', findings: [] };
  }
  if (!hasArtifact) {
    return {
      applicable: true,
      status: 'missing_artifact',
      findings: [{
        code: 'PROSE_EPISTEMICS_ARTIFACT_MISSING',
        severity: 'P2',
        counts_as_issue: true,
        path: ARTIFACT_REL,
        message: 'Prose epistemics manifest exists but data/prose-health/prose-health.json is missing. Run npm run prose:build-pilot-health.',
      }],
    };
  }

  try {
    const parsed = JSON.parse(readFileSync(artifactPath, 'utf-8')) as unknown;
    if (!isObject(parsed)) throw new Error('prose epistemics artifact must be an object');
    if (parsed.schema_version !== 1) throw new Error('prose epistemics artifact schema_version must be 1');
    return {
      applicable: true,
      status: 'present',
      summary: parseSummary(parsed.summary),
      coverage: parseCoverage(parsed.coverage),
      findings: parseFindings(parsed.findings),
    };
  } catch (err) {
    return {
      applicable: true,
      status: 'invalid_artifact',
      findings: [{
        code: 'PROSE_EPISTEMICS_ARTIFACT_INVALID',
        severity: 'P1',
        counts_as_issue: true,
        path: ARTIFACT_REL,
        message: err instanceof Error ? err.message : String(err),
      }],
    };
  }
}

function fmtRatio(value: number | null | undefined): string {
  return value === null || value === undefined ? 'n/a' : `${(value * 100).toFixed(1)}%`;
}

export function formatProseEpistemicsSummary(state: ProseEpistemicsState): string {
  if (!state.applicable) return 'Prose epistemics: not configured';
  if (state.status !== 'present' || !state.summary) {
    return `Prose epistemics: ${state.status.replaceAll('_', ' ')} findings=${state.findings.length}`;
  }
  return [
    `Prose epistemics: sources=${state.summary.declared_sources}`,
    `candidates=${state.summary.current_candidate_units}`,
    `promoted=${state.summary.promoted_units}`,
    `grounded=${state.summary.grounded_units}`,
    `unbacked=${state.summary.unbacked_units}`,
    `strict=${fmtRatio(state.coverage?.strict_grounding.ratio)}`,
    `findings=${state.findings.length}`,
  ].join(' ');
}
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
npx vitest scripts/health/__tests__/proseEpistemics.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/health/types.ts scripts/health/proseEpistemics.ts scripts/health/__tests__/proseEpistemics.test.ts
git commit -m "feat: read prose epistemics health artifact"
```

---

### Task 6: Health Checker And Report Integration

**Files:**
- Create: `scripts/health/checkers/proseEpistemics.ts`
- Test: `scripts/health/__tests__/checkers/proseEpistemics.test.ts`
- Modify: `scripts/health/context.ts`
- Modify: `scripts/health/checkers/index.ts`
- Modify: `scripts/health/scorer.ts`
- Modify: `scripts/health/bundle.ts`
- Modify: `scripts/health/reporter.ts`
- Modify: `scripts/health/index.ts`
- Modify: `scripts/health/__tests__/integration.test.ts`

- [ ] **Step 1: Write the failing checker test**

Create `scripts/health/__tests__/checkers/proseEpistemics.test.ts`:

```ts
import { describe, expect, it } from 'vitest';

import { proseEpistemicsChecker } from '../../checkers/proseEpistemics.ts';
import type { EntityInventory, HealthContext, ProseEpistemicsState } from '../../types.ts';
import { ALL_ENTITY_SCOPES } from '../../types.ts';

const emptyInventory = Object.fromEntries(ALL_ENTITY_SCOPES.map((scope) => [scope, []])) as EntityInventory;

function context(proseEpistemics?: ProseEpistemicsState): HealthContext {
  return {
    guideData: { models: {} } as HealthContext['guideData'],
    gitDates: {},
    inventory: emptyInventory,
    proseEpistemics,
  };
}

describe('proseEpistemicsChecker', () => {
  it('is silent when prose epistemics is not configured', async () => {
    const findings = await proseEpistemicsChecker.run(context({
      applicable: false,
      status: 'absent',
      findings: [],
    }));

    expect(findings).toEqual([]);
  });

  it('surfaces missing artifact as a catalog finding', async () => {
    const findings = await proseEpistemicsChecker.run(context({
      applicable: true,
      status: 'missing_artifact',
      findings: [{
        code: 'PROSE_EPISTEMICS_ARTIFACT_MISSING',
        severity: 'P2',
        counts_as_issue: true,
        path: 'data/prose-health/prose-health.json',
        message: 'missing',
      }],
    }));

    expect(findings).toEqual([{
      checkerId: 'prose-epistemics',
      code: 'PROSE_EPISTEMICS_ARTIFACT_MISSING',
      entityScope: 'catalog',
      entityId: '__prose-epistemics__',
      severity: 'P2',
      message: 'missing',
      dimension: 'prose-epistemics',
      sourcePath: 'data/prose-health/prose-health.json',
      details: {
        status: 'missing_artifact',
        sourceRef: undefined,
      },
    }]);
  });

  it('maps P4 issue findings without recomputing grounding', async () => {
    const findings = await proseEpistemicsChecker.run(context({
      applicable: true,
      status: 'present',
      findings: [{
        code: 'missing_grounding',
        severity: 'warning',
        counts_as_issue: true,
        source_ref: 'prose-source:x',
        path: 'docs/x.md',
        message: 'missing grounding report',
      }],
    }));

    expect(findings[0]).toMatchObject({
      checkerId: 'prose-epistemics',
      code: 'missing_grounding',
      entityScope: 'catalog',
      entityId: '__prose-epistemics__',
      severity: 'P2',
      dimension: 'prose-epistemics',
      sourcePath: 'docs/x.md',
      details: {
        status: 'present',
        sourceRef: 'prose-source:x',
      },
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
npx vitest scripts/health/__tests__/checkers/proseEpistemics.test.ts
```

Expected: FAIL because `checkers/proseEpistemics.ts` does not exist.

- [ ] **Step 3: Add the checker**

Create `scripts/health/checkers/proseEpistemics.ts`:

```ts
import type { Finding, HealthChecker, HealthContext, Severity } from '../types.ts';

function severityFromP4(value: string): Severity {
  if (value === 'error' || value === 'P1') return 'P1';
  if (value === 'warning' || value === 'P2') return 'P2';
  if (value === 'info' || value === 'P3') return 'P3';
  return 'P2';
}

export const proseEpistemicsChecker: HealthChecker = {
  id: 'prose-epistemics',
  name: 'Prose Epistemics',
  scope: 'catalog',
  dimensions: ['prose-epistemics'],

  async run(ctx: HealthContext): Promise<Finding[]> {
    const state = ctx.proseEpistemics;
    if (!state || !state.applicable) return [];

    return state.findings
      .filter((finding) => finding.counts_as_issue !== false)
      .map((finding) => ({
        checkerId: 'prose-epistemics',
        code: finding.code,
        entityScope: 'catalog',
        entityId: '__prose-epistemics__',
        severity: severityFromP4(finding.severity),
        message: finding.message,
        dimension: 'prose-epistemics',
        sourcePath: finding.path,
        details: {
          status: state.status,
          sourceRef: finding.source_ref ?? undefined,
        },
      }));
  },
};
```

- [ ] **Step 4: Run checker test to verify it passes**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
npx vitest scripts/health/__tests__/checkers/proseEpistemics.test.ts
```

Expected: PASS.

- [ ] **Step 5: Load prose epistemics in health context**

Modify `scripts/health/context.ts`:

1. Add the import:

```ts
import { loadProseEpistemics } from './proseEpistemics.ts';
```

2. In `buildContext`, after the existing optional `proseHealth` load, add:

```ts
  const proseEpistemics = loadProseEpistemics(REPO_ROOT);
  if (proseEpistemics.applicable) {
    const meta = resolveArtifact('data/prose-health/prose-health.json', false);
    if (meta) artifacts.push(meta);
  }
```

3. In the returned `context` object, include:

```ts
    proseEpistemics,
```

- [ ] **Step 6: Register the checker and declare it unscored**

Modify `scripts/health/checkers/index.ts`:

```ts
import { proseEpistemicsChecker } from './proseEpistemics.ts';
```

Add `proseEpistemicsChecker` after `proseQualityChecker` in the `checkers` array.

Modify `scripts/health/scorer.ts` and add this entry to `UNSCORED_CHECKERS`:

```ts
  // Coverage-ramp reader: P4 already computes epistemic denominators and ratios.
  // Natural-systems health surfaces its findings and dashboard but does not fold
  // the ramp into the existing 0-1 project score.
  'prose-epistemics',
```

- [ ] **Step 7: Carry prose epistemics through bundle, reporter, and JSON output**

Modify `scripts/health/bundle.ts`:

1. Import the type:

```ts
import type { ProseEpistemicsState } from './types.ts';
```

2. Add to `BuildHealthBundleResult`:

```ts
  proseEpistemics?: ProseEpistemicsState;
```

3. Add to the returned object in `buildHealthBundle`:

```ts
    proseEpistemics: context.proseEpistemics,
```

Modify `scripts/health/reporter.ts`:

1. Add imports:

```ts
import type { ProseEpistemicsState } from './types.ts';
import { formatProseEpistemicsSummary } from './proseEpistemics.ts';
```

2. Add to `DashboardInput`:

```ts
  proseEpistemics?: ProseEpistemicsState;
```

3. In the "Coverage Dashboard" block, after prose coverage lines, add:

```ts
      if (result.proseEpistemics?.applicable) {
        lines.push(`  ${formatProseEpistemicsSummary(result.proseEpistemics)}`);
      }
```

Modify `scripts/health/index.ts`:

1. Add `proseEpistemics: bundle.proseEpistemics,` to `filteredResult`.
2. Add `proseEpistemics: bundle.proseEpistemics,` to `scoredReport`.

- [ ] **Step 8: Update integration test expectations**

Modify `scripts/health/__tests__/integration.test.ts` in the first full-run test:

```ts
    expect(report.proseEpistemics).toBeDefined();
    expect(report.proseEpistemics.applicable).toBeTypeOf('boolean');
```

Add a focused checker test near the checker-filter tests:

```ts
  it('can run only the prose epistemics checker', { timeout: HEALTH_COMMAND_TIMEOUT_MS }, () => {
    const result = runHealthCommand(['--checker=prose-epistemics', '--no-fail', '--format=json']);
    expect(result.status).toBe(0);
    expect(result.report.checkers).toEqual(['prose-epistemics']);
    expect(result.report.proseEpistemics).toBeDefined();
  });
```

- [ ] **Step 9: Run targeted tests**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
npx vitest scripts/health/__tests__/proseEpistemics.test.ts scripts/health/__tests__/checkers/proseEpistemics.test.ts scripts/health/__tests__/integration.test.ts --run
```

Expected: PASS.

- [ ] **Step 10: Run typecheck and health**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
npm run typecheck
npm run health -- --checker=prose-epistemics --no-fail
```

Expected: typecheck passes; health prints the prose epistemics summary or an explicit missing/invalid artifact finding.

- [ ] **Step 11: Commit**

```bash
git add scripts/health/proseEpistemics.ts scripts/health/checkers/proseEpistemics.ts scripts/health/__tests__/proseEpistemics.test.ts scripts/health/__tests__/checkers/proseEpistemics.test.ts scripts/health/__tests__/integration.test.ts scripts/health/types.ts scripts/health/context.ts scripts/health/checkers/index.ts scripts/health/scorer.ts scripts/health/bundle.ts scripts/health/reporter.ts scripts/health/index.ts
git commit -m "feat: surface prose epistemics in health"
```

---

### Task 7: Pilot Validation And Regression Checks

**Files:**
- Generated/modified by command: `data/prose-health/prose-health.json`
- Generated/modified by command: `doc/reports/health-report.json`
- Optional docs update: `doc/reports/prose-epistemics-pilot.md`

- [ ] **Step 1: Run the full prose epistemics pilot loop**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
npm run prose:write-pilot-decompositions
uv run science annotate ingest-prose-decomposition data/prose-decomposition-inputs/pilot/cole-hopf-morphism-analysis.json --root .
uv run science annotate ingest-prose-decomposition data/prose-decomposition-inputs/pilot/tropical-dequantization-functor-backbone.json --root .
uv run science annotate ingest-prose-decomposition data/prose-decomposition-inputs/pilot/universality-classes-two-faces.json --root .
npm run prose:build-pilot-health
npm run health -- --no-fail
```

Expected: all commands succeed. Health output includes a `Prose epistemics:` line in the coverage dashboard.

- [ ] **Step 2: Inspect P4 artifact invariants**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
node -e "const r=require('./data/prose-health/prose-health.json'); console.log(JSON.stringify({summary:r.summary, coverage:r.coverage, findings:r.findings}, null, 2))"
```

Expected:

- `summary.declared_sources` is `3`
- `summary.current_candidate_units` is `3`
- `summary.promoted_units` is `3`
- `summary.skipped_units` is `3`
- `coverage.promotion.denominator` is `3`
- `coverage.strict_grounding.denominator` is `3`

`grounded_units` may be `0` at pilot start; that is expected until evidence lines exist.

- [ ] **Step 3: Verify fingerprint-preserved re-ingest**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
cp data/prose-decompositions/cole-hopf-morphism-analysis/index.json /tmp/cole-hopf-index-before.json
npm run prose:write-pilot-decompositions
uv run science annotate ingest-prose-decomposition data/prose-decomposition-inputs/pilot/cole-hopf-morphism-analysis.json --root .
node -e "const before=require('/tmp/cole-hopf-index-before.json'); const after=require('./data/prose-decompositions/cole-hopf-morphism-analysis/index.json'); const promoted=Object.values(after.units).filter(u=>u.promoted_to); if (promoted.length !== 1) throw new Error('expected one promoted fingerprint after re-ingest'); console.log('promoted fingerprint preserved')"
```

Expected: prints `promoted fingerprint preserved`.

- [ ] **Step 4: Smoke-check unit renumbering does not inflate current denominators**

This is a lightweight denominator/display regression, not comprehensive join-stability
coverage. The shipped P3/P4 join is fingerprint-based, so a pure `unit_id` renumber should
be invisible to grounding joins by construction. This check mainly guards against a future
consumer accidentally treating `unit_id` as denominator identity.

Edit `scripts/prose-epistemics/write-pilot-decompositions.ts` temporarily by changing only `cole-hopf-morphism-analysis` unit `u001` to `u010`, leaving the quote unchanged. Re-run:

```bash
cd ~/d/natural-systems-prose-epistemics
npm run prose:write-pilot-decompositions
uv run science annotate ingest-prose-decomposition data/prose-decomposition-inputs/pilot/cole-hopf-morphism-analysis.json --root .
npm run prose:build-pilot-health
node -e "const r=require('./data/prose-health/prose-health.json'); if (r.summary.current_candidate_units !== 3) throw new Error('candidate denominator changed after renumber'); console.log('renumber did not change current candidate denominator')"
```

Expected: prints `renumber did not change current candidate denominator`.

Restore the temporary `u010` edit back to `u001` with this patch, then regenerate,
re-ingest, and rebuild health:

```patch
*** Begin Patch
*** Update File: scripts/prose-epistemics/write-pilot-decompositions.ts
@@
-      unit_id: 'u010',
+      unit_id: 'u001',
*** End Patch
```

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
npm run prose:write-pilot-decompositions
uv run science annotate ingest-prose-decomposition data/prose-decomposition-inputs/pilot/cole-hopf-morphism-analysis.json --root .
npm run prose:build-pilot-health
```

Expected: working tree no longer contains the temporary unit-id change.

- [ ] **Step 5: Add a pilot report**

Create `doc/reports/prose-epistemics-pilot.md`:

````markdown
# Prose Epistemics Pilot

Date: 2026-06-19

Pilot sources:

- `prose-source:cole-hopf-morphism-analysis`
- `prose-source:tropical-dequantization-functor-backbone`
- `prose-source:universality-classes-two-faces`

Operator commands:

```bash
npm run prose:write-pilot-decompositions
npm run prose:build-pilot-health
npm run health -- --no-fail
```

Current interpretation:

- Promotion coverage is expected to reach 3/3 for the reviewed pilot candidate units.
- Strict grounding may start at 0/3 because the pilot's promoted propositions need explicit evidence lines.
- Unbacked units are the evidence-authoring queue, not a failed release gate.
````

- [ ] **Step 6: Run final verification**

Run:

```bash
cd ~/d/natural-systems-prose-epistemics
npx vitest scripts/prose-epistemics/__tests__/config.test.ts scripts/prose-epistemics/__tests__/write-pilot-decompositions.test.ts scripts/prose-epistemics/__tests__/build-pilot-health.test.ts scripts/health/__tests__/proseEpistemics.test.ts scripts/health/__tests__/checkers/proseEpistemics.test.ts --run
npm run typecheck
npm run health -- --no-fail
uv run science health --format json
git diff --check
```

Expected: all commands pass. `uv run science health --format json` includes `prose_epistemics.applicable: true`.

- [ ] **Step 7: Commit**

```bash
git add data/prose-decomposition-inputs data/prose-decompositions data/prose-grounding data/prose-health doc/reports/prose-epistemics-pilot.md doc/reports/health-report.json entities/prose-sources entities/propositions knowledge/graph.trig knowledge/sources scripts package.json
git commit -m "test: validate prose epistemics pilot"
```

---

## Self-Review Checklist

- Spec coverage:
  - Manifest denominator: Task 1.
  - Markdown-only P2 decomposition artifacts: Task 2.
  - P2 ingest/check and one-unit promotion: Task 3.
  - Pinned grounding floor and `npm run kg:build`: Task 4.
- P4 artifact consumer, not TS recomputation: Tasks 5 and 6.
- Natural-systems health visibility: Task 6.
- Fingerprint-preserved re-ingest and renumber denominator smoke check: Task 7.
- Placeholder scan:
  - No placeholder markers or unspecified test steps remain.
- Type consistency:
  - `ProseEpistemicsState` is defined in `types.ts`, loaded by `proseEpistemics.ts`, attached to `HealthContext`, carried by `bundle.ts`, rendered by `reporter.ts`, and emitted by `index.ts`.
  - Checker id is consistently `prose-epistemics`; dimension is consistently `prose-epistemics`; it is deliberately listed in `UNSCORED_CHECKERS`.

## Execution Handoff

Plan complete and saved to `docs/plans/2026-06-19-natural-systems-prose-epistemics-application-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
