---
name: project-imaging-x-discovery
description: >-
  Search, rank, and help download medical imaging datasets with a
  structured local index of 1100+ records from Project-Imaging-X.
  After local-index results, always runs one supplementary web search
  for additional hits. Use when the user asks for dataset discovery,
  open-only filtering, platform-specific search, or download guidance
  across modalities, anatomies, diseases, and tasks.
---

# Project-imaging-x-discovery

Use this skill for medical imaging dataset discovery and single-dataset download assistance.
Default to the local index first (deterministic scripts). **After** presenting local-index tables in a discovery flow, **always** run **one** supplementary web search—see §4 (skip §4 only when you are in single-dataset follow-up mode per §5).
Resolve `scripts/...` and `references/...` paths relative to this skill directory, not the user's working directory.

## Files

- `datasets.json`: local dataset index
- `access_rules.json`: URL pattern to access/download rule mapping
- `scripts/search_datasets.py`: deterministic filtering and ranking
- `scripts/lookup_dataset.py`: deterministic single-dataset lookup for follow-up download help
- `scripts/update_index.py`: refresh the local index
- `references/query-normalization.md`: map user language to search arguments
- `references/ranking-policy.md`: strict-vs-near and ranking rules

## Workflow

### 1. Translate the request into explicit constraints

Extract only the constraints the user actually stated:

- modality
- anatomy / structure
- disease
- task
- dimension
- label requirement
- access requirement
- platform requirement

If you need mapping help, read [references/query-normalization.md](references/query-normalization.md).

Treat these as hard constraints unless the user phrased them as a preference such as `prefer`, `ideally`, or `最好`.

### 2. Run the deterministic search script first

Use `scripts/search_datasets.py` instead of manually filtering in prose.

Example:

```bash
python /path/to/project-imaging-x-discovery/scripts/search_datasets.py \
  --modality mr \
  --structure brain \
  --disease glioma \
  --task seg \
  --dim 3d \
  --label true \
  --access open \
  --prefer-open
```

The script returns:

- `interpreted_query`
- `strict_match_count`
- `strict_matches`
- `near_match_count`
- `near_matches`

### 3. Present strict matches first

Strict matches satisfy all hard constraints. Near matches are only for fallback.

Never mix them in one main table.
When `scripts/search_datasets.py` already returns ranked strict matches, preserve that order in the main strict table instead of replacing the first rows with hand-picked examples.

If the user asked for `open`, `public`, `direct download`, or `公开可下载`:

1. `access=open` stays in the main strict result set
2. `registration` and `application` move to near matches unless the user explicitly accepted them
3. If you still mention a non-open benchmark such as BraTS, state that it is a high-value fallback that does not satisfy the open requirement

When the user did not state an access requirement, rank by the policy in [references/ranking-policy.md](references/ranking-policy.md).

### 4. Supplementary web search (always after discovery)

The local index covers 1100+ datasets but may miss very recent or niche entries.
**After** you present strict and near tables from §3, **always** perform **one** targeted web search in addition to those hits—**regardless of** `strict_match_count` (0, a few, or many). The goal is extra coverage beyond the frozen index snapshot.

**Skip §4** only when §5 applies: the user has **already named a single dataset** and you are in follow-up lookup/download mode (no broad discovery in this turn).

**Rules — keep it surgical, not broad:**

1. Construct a narrow query that targets what the index may have missed (recent years, alternate names, niche hosts). Example template when helpful:
   ```
   "<specific_disease_or_anatomy>" "<modality>" dataset download site:kaggle.com OR site:zenodo.org OR site:huggingface.co OR site:grand-challenge.org OR site:cancerimagingarchive.net
   ```
2. Limit to **1 web search call** for this supplementary step (not multiple).
3. From the search results, only add datasets that are **not** already in your strict/near tables (compare by name or URL).
4. Mark web-sourced additions clearly (e.g. a `Source` column with values `index` vs `web supplement`). Do not pretend web hits came from the local index.
5. For web-sourced rows, access is unknown unless you can infer it from the URL pattern (use the same logic as `access_rules.json` when applicable).
6. If the web search finds **nothing new** beyond the index, state briefly that the supplementary search did not add further datasets—**still** report that the step ran.

If the user asked for a rare modality and the local index has no real coverage for it, say that explicitly in the index-backed section, avoid padding with irrelevant near matches from other modalities, and let the supplementary search carry additional coverage.

### 5. Download assistance is one dataset at a time

Do not bulk download.

If the user has already selected a specific dataset, skip broad discovery (including **§4 supplementary web search**) and switch straight to single-dataset lookup.
In that follow-up mode:

1. Use `scripts/lookup_dataset.py` before any manual prose filtering or broad search
2. `strict_matches` must contain only the selected dataset when lookup is unambiguous
3. `near_matches` stays empty unless the lookup itself is ambiguous
4. Do not re-run broad candidate search unless the selected name cannot be resolved
5. Reuse the resolved dataset's exact `download_method` and `auth_instructions`; do not replace them with a generic recipe from another platform
6. If the user explicitly says the dataset is already selected, attempt lookup on the exact provided name first even if the token looks generic, short, or resembles a modality/platform label
7. If that lookup is unresolved, stop and ask for the exact dataset name instead of falling back to broad discovery in the same turn

For `access=open`:

1. Ask for explicit confirmation on one chosen dataset
2. If the user names a dataset, use `scripts/lookup_dataset.py` to pull its exact metadata first
3. Download only after confirmation
4. Default to the working directory or a user-specified path
5. Warn before downloads larger than 10 GB

For `access=registration` or `application`:

1. Do not start the download by default
2. Surface `auth_instructions`
3. If the user names a dataset, use `scripts/lookup_dataset.py` before describing access steps
4. Only continue if the user says credentials or approval are already in place
5. Keep the next step focused on login, registration, approval, and the official portal; do not mention unrelated direct-download tools such as `wget`, `curl`, or `gdown` unless the user explicitly asks for alternatives after access is granted

For `access=unknown`:

1. Say that local index access is unresolved
2. If the user explicitly asks for the exact next step or download path, inspect the official landing page once to resolve it
3. Mark any resolved path as `web-confirmed` rather than pretending it came from the local index alone
4. If the page still does not make access clear, stop at `unresolved`

If `scripts/lookup_dataset.py` returns multiple matches:

1. Do not pretend the selected name resolved uniquely
2. Put the exact family or version candidates in `strict_matches`
3. Put weaker or derived variants in `near_matches`
4. Explain the disambiguation in `interpreted_query`
5. Give the shared next access step only at the family level unless one variant is clearly selected

If `scripts/lookup_dataset.py` returns `resolution_mode=unresolved` for a short or generic query:

1. Do not guess the dataset
2. Keep `strict_matches` empty
3. Explain that the provided name is too short or too generic to resolve safely
4. Ask for the exact dataset name before giving download steps

## Output Contract

Use this shape by default:

```text
interpreted_query:
- modality
- structure
- disease
- task
- dim
- label
- access
- platform

strict_matches:
- markdown table

near_matches:
- markdown table
- each item includes why it is near rather than strict

web_supplement (after §4, discovery flows only):
- optional extra rows or short list from the mandatory web search
- each web-only row marked `web supplement`; state explicitly that one supplementary search ran

download_next_step:
- what can be downloaded now
- what requires registration or application
- keep it concrete and short; do not add extra option menus unless the user asked for alternatives
```

## Edge Rules

- In discovery flows, do not skip the **one** supplementary web search in §4 unless §5 single-dataset follow-up applies
- Do not invent dataset names, access rules, or direct download URLs
- Do not mix strict and near matches into one primary recommendation list
- Do not let a famous benchmark outrank a stricter open result when the user asked for open access
- Do not treat landing pages as direct file URLs without checking
- If the user asks about commercial use or license, say the index does not track that and point them to the official page

## Updating the Index

Refresh the local index only when needed:

```bash
python /path/to/project-imaging-x-discovery/scripts/update_index.py --github
```
