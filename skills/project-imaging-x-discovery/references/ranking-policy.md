# Ranking Policy

Always separate strict matches from near matches.

## Strict Matches

A strict match satisfies every stated hard constraint:

- modality
- anatomy
- disease
- task
- dimension
- label requirement
- access requirement
- platform requirement

## Near Matches

Use near matches only when:

- strict matches are too few for a useful answer, or
- the user explicitly asks for alternatives

Every near match must state why it is not strict. Common reasons:

- `access=registration`
- `label=False`
- `dim=2D`
- `task=Cls`
- `diseases=Brain Tumor` rather than `Glioma`

## Sorting

When the user mentions `open`, `public`, `directly downloadable`, or `公开可下载`:

1. Sort `access=open` before all other access types
2. Within the same access tier, prefer:
   - `label=true`
   - larger sample size
   - newer year
   - non-empty URL

When the user does not state an access preference:

1. Prefer `label=true`
2. Prefer larger sample size
3. Prefer newer year
4. Use access type as a secondary qualifier, not the lead ranking factor

## Output Contract

Present results in this order:

1. `interpreted_query`
2. `strict_matches`
3. `near_matches`
4. `download_next_step`

Never mix strict and near matches into one primary table.
