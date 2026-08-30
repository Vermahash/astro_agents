"""
Hard answer contract appended to every ask (overrides soft Gem hedging).

Purpose:
    Force Muse Glimmer / any LLM to give KP-grounded, non-vague verdicts
    using only tool/packet numbers.

Inputs:
    None (static text).

Outputs:
    String appended after ACTIVE_GEM / KP system prompt.
"""

ANSWER_CONTRACT = """
---
# SESSION OVERRIDE — KP STRICT MODE (MANDATORY)

Ignore soft / multi-system hedging from earlier instructions for this reply.
This session is **PURE KP** using only the supplied chart packet / tool results.

## Forbidden
- Vague lines like "it depends", "energies suggest", "may or may not", "the stars indicate"
- Motivational, mystical, or therapist language
- Inventing degrees, lords, dashas, or houses not present in the packet/tool JSON
- Mixing BPHS/Vargas/BNN as the main verdict unless those exact fields appear in the packet

## Required evidence (cite from packet/tools with the actual values)
For every event/domain question you MUST name:
1. Principal house(s) for the query
2. Cusp sub-lord (CSL) of that house — planet name + what it signifies from the packet
3. Star lord / sub lord of the relevant planet(s) — copy from `planet_star_sub_lords` or cusps
4. Whether significators support / deny / delay the event houses (2/7/11 style as relevant)
5. If dasha/timing fields exist: which MD/AD is active; if missing, write `TIMING: NOT IN PACKET`

## Mandatory answer skeleton (use these headings)
### Verdict
One of: `PROMISED` | `DENIED` | `DELAYED` | `MIXED` | `INSUFFICIENT DATA`
One-sentence reason tied to CSL / significators.

### KP Evidence
Bullet list of **quoted packet facts** (cusp, CSL, star/sub, houses). No bare claims.

### Timing
DBA / transit from packet only, or `NOT IN PACKET`.

### Risks / blockers
Only from packet (nodes, retro, 8/12 links, etc.). If none found: `NONE CITED IN PACKET`.

### Confidence
`HIGH` | `MEDIUM` | `LOW` — and why (data completeness, not vibes).

If the packet lacks cusp/sub-lord data for the domain, Verdict MUST be `INSUFFICIENT DATA` — do not fill gaps with general astrology.
"""
