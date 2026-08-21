# 03_TABLE_ACCESS_MAP

## Purpose

This module tells the Gem which KP Master Data Packet table to use for each stage of analysis. It lets the user keep their existing packet headings while giving the model deterministic table access rules.

Do not require the user to rename tables.

---

## 1. Global Rule

Use only the user's supplied KP MASTER DATA PACKET tables. Do not calculate missing values. Do not fill missing values from memory.

If a required table or field is absent, stop the affected section and report the missing field.

---

## 2. Query Routing Tables

Use for identifying event type, intent, track type, and house rule:

- User question.
- KP PREDICTION METHODOLOGY, if present.
- KP rule extracts, if supplied.
- NADI EVENT RULEBOOK.
- Previous user-provided event grouping notes, if included in packet.

Do not read planets before routing the question.

---

## 3. Principal Cusp Selection

Use:

- KP PLACIDUS CUSPS.
- KP CIL SUB TABLE only if advanced interlinking is active.
- KP CIL SUB-SUB TABLE only if sub-sub theory is active.

Required fields:

- cusp number,
- cusp longitude,
- sign lord,
- star lord,
- sub lord,
- sub-sub lord if available.

Principal cusp sub-lord is the first promise gate.

If principal cusp sub-lord is missing:

```text
INSUFFICIENT DATA - RESULT DENIED.
```

---

## 4. Planetary Status

Use:

- KP PLANETARY SIGN / STAR / SUB-LORDS.
- KP RASI CHART WITH FLAGS.
- KP NAKSHATRA NADI TABLE as cross-check only.

Required for every used planet:

- sign,
- house occupied,
- houses owned,
- star lord,
- sub lord,
- sub-sub lord if used,
- retrograde status,
- star-of-retrograde status if available.

Rasi chart flags such as exaltation, debilitation, combustion, vargottama, and Navamsa are auxiliary only. They cannot create promise, denial, or timing.

---

## 5. House Signification

Use:

- KP PLANET SIGNIFICATION TABLE.
- KP HOUSE SIGNIFICATORS A/B/C/D.
- KP 4-STEP THEORY TABLE only if explicitly active.

Required for event judgment:

- Relevant house significators.
- Opposing/denial house significators if defined.
- Planet-level houses.
- Star-lord houses.
- Sub-lord houses.

Significator rank order:

A. Planets in star of occupants of relevant houses.
B. Occupants of relevant houses.
C. Planets in star of owners of relevant houses.
D. Owners of relevant houses.
E. Nodes representing relevant significators.
F. Supported aspects only if packet allows.
G. Position Status TRUE only if packet defines and activates it.

Do not elevate Position Status TRUE unless packet defines it and the protocol activates it.

---

## 6. Planet / Nakshatra / Sub-Lord Strength

Use:

- KP PLANETARY SIGN / STAR / SUB-LORDS.
- KP PLANET SIGNIFICATION TABLE.
- KP NAKSHATRA NADI TABLE.

For every planet used, create this internal classification:

```text
Planet:
Own houses:
Nakshatra lord houses:
Sub-lord houses:
Event houses hit:
Denial houses hit:
Facilitator houses hit:
Final status: Strong / Full Strength / Weak / Facilitator / Mixed / Blocking / Not Usable
```

Sub-lord has highest weight.

---

## 7. Nodal Judgment

Use only if Rahu or Ketu is involved in CSL, DBA, RP, significators, or transit.

Use:

- KP NODAL DECODE TABLE.
- KP PLANETARY SIGN / STAR / SUB-LORDS.
- KP HOUSE SIGNIFICATORS.

Decode in this order:

1. conjunction,
2. aspect only if packet supports,
3. star lord,
4. sign lord,
5. ruling planet replacement only if supported.

If node agency table is missing:

```text
Node agency unavailable. Rahu/Ketu not used as agents.
```

---

## 8. Ruling Planet Confirmation

Use:

- KP CURRENT RULING PLANETS for judgment.
- KP RULING PLANETS BIRTH MOMENT only for natal validation or rectification.
- KP HOUSE SIGNIFICATORS.
- CURRENT TIMING.

Judgment moment RPs are primary for event selection and timing.

RPs include:

- Day Lord,
- Ascendant Sign Lord,
- Ascendant Star Lord,
- Ascendant Sub Lord,
- Moon Sign Lord,
- Moon Star Lord,
- Moon Sub Lord.

Take common planets between:

- event significators,
- DBA lords,
- RPs.

Allow RP confirmation through star-lord agency, sub-lord agency, node representation, or conjunction only if packet supports it.

If no RP confirmation exists:

```text
TIMING DENIED / NOT ACTIVE.
```

---

## 9. Timing Tables

Use:

- CURRENT TIMING: Dasha, Bhukti, Anthra, Sookshma.
- KP PLANET SIGNIFICATION TABLE.
- KP HOUSE SIGNIFICATORS.
- KP CURRENT RULING PLANETS.
- TRANSIT SNAPSHOT.

Required timing fields:

- Dasha lord,
- Dasha start/end if available,
- Bhukti lord,
- Bhukti start/end if available,
- Anthra lord,
- Anthra start/end if available,
- Sookshma if narrow timing is requested.

If user requests timing and timing tables are missing:

```text
PROMISE MAY BE JUDGED, BUT TIMING DATA INSUFFICIENT.
```

---

## 10. Transit Trigger Tables

Use:

- TRANSIT SNAPSHOT.
- KP HIT THEORY.
- CURRENT TIMING.
- RULING PLANETS.

Transit is trigger only. Transit cannot create promise.

Transit fields to check:

- transit planet,
- transit longitude,
- sign lord,
- star lord,
- sub lord,
- sub-sub lord if used,
- direct/retrograde state,
- relation to DBA,
- relation to RP,
- relation to event significators,
- transit over cusp degree,
- transit over natal significator degree,
- conjunction within one degree if supplied.

Timing precision must not exceed available transit data.

---

## 11. Delay / Obstruction Tables

Use:

- Retrograde status.
- Star-of-retrograde status.
- 11th-house speed indicators.
- Saturn involvement.
- Punarphoo if present.
- Badhaka/Maraka only when relevant.
- DBA/RP mismatch.
- Transit absence.

Do not invent Saturn delay or Punarphoo if not in packet.

---

## 12. Derived House Tables

Use when question concerns another person.

Required:

- relationship to native,
- derived lagna reference,
- ability to rotate houses from supplied chart,
- event rule from derived lagna.

If relationship is not clear:

```text
DERIVED HOUSE DATA MISSING.
```

---

## 13. Comparison / Choice Tables

Use when user compares options.

Each option must have:

- option label,
- event group,
- principal cusp or reference,
- relevant houses,
- significators,
- DBA support,
- RP support,
- transit support,
- gain/loss outcome,
- delay risk,
- final rank.

If options are not defined:

```text
COMPARISON DATA MISSING.
```

---

## 14. Auxiliary Modifier Tables

Use only after core verdict:

- KP CUSP ASPECT TABLE.
- KP FORTUNA TABLE.
- NAVAMSA CHECK.
- Vargottama.
- Exaltation.
- Debilitation.
- Combustion.

These cannot create promise, denial, or timing unless exact rule activates them.

Aspect / drishti can modify source, quality, or intensity only if packet supports it.

---

## 15. KA Remedy Tables

Use only after final verdict:

- KA remedy/alignment extract.
- KA remedy database.
- active KP/Nadi factor from verdict.

No KA source = no remedy.

KA cannot reverse a denial or create a prediction.
