# 02_NADI_EVENT_RULEBOOK

## Purpose

This module supplies the house combinations, event routes, facilitator houses, obstruction houses, and event subtypes used by BRAHMA-DAIVAGYA when exact KP event rules are absent.

Use this file only for house/event combination logic. Do not use it as a remedy source. Do not let it override exact KP rules.

Default use:

```text
KP decides promise and timing discipline.
Nadi supplies house/event combinations.
```

---

## 1. Foundational Rules

### 1.1 Single house does not give the event

Never judge an event from one house alone. A few houses combine to fructify an event.

For every event:

1. identify main house,
2. identify supporting houses,
3. identify facilitator houses,
4. identify obstruction/denial houses,
5. check Planet/Nakshatra/Sub-lord layers,
6. check DBA,
7. check transit only after DBA supports.

### 1.2 Planet / Nakshatra / Sub-lord strength

Strength order:

```text
Sub-lord > Nakshatra lord > Planet
```

Classify every used planet:

- Strong: sub-lord signifies full event combination and nakshatra/planet support it.
- Full Strength: planet and nakshatra do not negate and support a sub-lord that signifies full event combination.
- Weak: nakshatra/planet support event but sub-lord is weak, mixed, or facilitator-only.
- Facilitator: only facilitator houses appear; other DBA lords must carry the event.
- Blocking: sub-lord signifies event-denial or obstruction combination.
- Mixed: event and denial houses both appear in major layers.
- Not Usable: no relevant connection.

### 1.3 DBA hierarchy

Use Vimshottari DBA.

```text
Dasha > Bhukti > Anthra > Sookshma
```

If Dasha does not allow the event, current period cannot deliver.
If Bhukti does not allow, event does not materialize cleanly.
If Anthra does not allow, event does not occur in that Anthra.
If DBA supports but transit does not, promise exists but timing is not active.

### 1.4 12th-from-house principle

The 12th from a house can mar, separate, reduce, consume, release, or obstruct that house. Apply only through the event rule, not blindly.

Examples:

- 9th is 12th from 10th and may separate from job/status.
- 6th is 12th from 7th and may separate from marital home.
- 5th is 12th from 6th and may release from disease/litigation.
- 4th is 12th from 5th and may deny children, but 4th supports education.
- 3rd is 12th from 4th and may deny property, but 3rd supports vehicles because it is travel.
- 10th is 12th from 11th but can be good for business because 10th and 11th are complementary in that context.

If no event-specific denial rule exists:

```text
DENIAL HOUSE SOURCE = NOT DEFINED
```

Do not invent denial.

---

## 2. Core House Meanings for Routing

Use this section only for routing, not final verdict.

| House | Routing Meaning |
|---|---|
| 1 | self, body, identity, initiative, health baseline |
| 2 | money received, stored wealth, family, speech, addition to family |
| 3 | communication, documents, writing, short travel, courage, movement away from home, siblings |
| 4 | home, property, vehicle, mother, residence, education base, homeland, mental peace |
| 5 | children, pregnancy, intelligence, love, speculation, creativity, comprehension |
| 6 | service job, disease, debt, litigation, competition, enemy, work conditions |
| 7 | marriage, spouse, partner, public dealing, contract, buyer/seller, opponent |
| 8 | delay, danger, surgery, chronicity, inheritance, obstacle, hidden matters, insult |
| 9 | long travel, foreign link, higher education, fortune, father/guru, law, pilgrimage |
| 10 | career, profession, action, status, authority, recognition, fame |
| 11 | fulfillment, gains, realization, network, success, elder sibling |
| 12 | loss, expense, foreign residence, hospital, isolation, confinement, withdrawal |

No house is universally good or bad. Meaning depends on the event.

---

## 3. Event Rule Database

### 3.1 Education

Core houses:

```text
2, 4, 9, 11
```

Meanings:

- 2 = knowledge acquired.
- 4 = prime education / primary education.
- 9 = higher education.
- 11 = gain in education.

Facilitators:

- 5 = intelligence and comprehension.
- 3 = written work, communication, printing.

Good education combinations:

| Combination | Meaning |
|---|---|
| 4,9,11 | highest / A grade |
| 4,11 | above average / B grade |
| 5,11 | intelligent, above average |
| 4,5,9 | average / C grade |
| 2,4,5,9 scattered | low / D grade |

Failure / obstacles:

```text
6, 8, 12
```

No education:

```text
repeated 6,8,12 in DBA with malefic influence on 4th
```

No inclination:

```text
3,6,8
3,6,12
3,8,12
```

Scholarship:

```text
6,11
```

Competitive exam success:

```text
6,11
4,9,11
4,11
5,11
```

Interview / group discussion:

```text
3,11
3,6,11
```

Foreign education:

```text
Education Track + Foreign Travel Track
```

Educational writing/publication/fame:

```text
3,10,11
```

Teaching/research:

```text
3,4,5,9,11
```

Track classification:

- Education = Essential.
- Foreign education = Education Essential + Foreign Modifier/Essential depending wording.
- Scholarship = Outcome.
- Interview = Process.
- Failure = Negative Risk.
- Field selection = Outcome/Advisory.

---

### 3.2 Litigation

Core litigation houses:

```text
6, 8, 12
```

Meanings:

- 6 = litigation, dispute, enemy, contest.
- 8 = tension, obstacles, insult, failure.
- 12 = expenses, penalties, loss, imprisonment, hidden enemy.

Litigation arises when any two or all of 6,8,12 combine in Planet/Nakshatra/Sub-lord or DBA, especially with natural malefics.

Do not create litigation from only one of 6, 8, or 12.

Imprisonment / arrest:

```text
2,3,8,12
```

Political confinement:

```text
2,3,12
```

Going underground:

```text
3,4,8,12
```

House arrest:

```text
4,8,12
```

Kidnapping:

```text
2,3,4,8,12
```

Winning litigation:

| Combination | Relative strength |
|---|---|
| 6,11 | strongest |
| 10,11 | next |
| 6,10 | next |
| 1,6 | next |

Compromise:

```text
5,9
```

Forgery/cheating type litigation:

```text
3,6,8 with Mercury/Neptune/Jupiter if packet supports
```

Track classification:

- Litigation existence = Essential.
- Winning = Outcome.
- Settlement = Outcome.
- Compromise = Modifier/Outcome.
- Arrest/imprisonment = Negative Risk.
- Legal expense = Outcome/Negative Risk.

---

### 3.3 Property

Property purchase:

```text
4,11,12
```

Meanings:

- 4 = property.
- 11 = gain/fulfillment.
- 12 = expense for purchase.

Natural significators:

```text
Mars and/or Saturn
```

They must be involved by DBA, aspect, conjunction, or transit if the packet follows Nadi property logic.

Property through loan:

```text
4,6,11,12
```

Property through provident fund/insurance:

```text
4,8,11,12
```

Property through legacy:

```text
4,8,11
```

No 12th required if no expense is made.

Joint-name property:

```text
3 with purchase combination
```

3 restricts whole ownership because it is 12th from 4th.

Purchase in installments:

```text
4,12
```

Commercial property:

```text
7 + Mercury + property purchase combination
```

Construction:

```text
same purchase combination; check malefic obstruction if construction trouble is asked
```

Rental income:

```text
4,6,11
```

Loss of property:

```text
3,6,8,12 with malefics
```

Demolition / government loss:

```text
4,8,12 with Sun/Moon/government factor if supplied
```

Sale of property:

```text
3,5,10
```

Sale above market:

```text
3,5,10 + 11
```

Sale below market:

```text
3,5,10 + 6,8,12
```

Simultaneous sale and purchase:

```text
3,5,10 + 4,11
```

Change of residence:

```text
3,5 with separative planets
```

Track classification:

- Purchase = Essential.
- Loan = Modifier.
- Commercial = Modifier.
- Sale = Essential if asked.
- Profit/loss = Outcome.
- Construction = Process.
- Loss/demolition = Negative Risk.
- Residence change = Separate Event Track.

---

### 3.4 Vehicle

Vehicle purchase:

```text
4,11,12
```

Facilitator:

```text
3 = short travel / movement
```

Natural significator:

```text
Venus
```

Vehicle through loan:

```text
4,6,11,12 + Venus
```

Vehicle through provident fund/insurance:

```text
4,8,11,12
```

Vehicle gift / lottery:

```text
3,4,5,8,10,11 + Venus
```

Commercial vehicle:

```text
7 + Mercury + vehicle combination
```

Vehicle theft:

```text
4,6,8,12 with Rahu/Ketu
```

Vehicle snatching:

```text
4,7,8,12 with Rahu/Ketu
```

Vehicle recovery:

```text
2,6,10,11
or
4,11
```

Sale of vehicle:

```text
3,5,10 + Venus
```

Sale above market:

```text
3,5,10 + 11
```

Sale below market:

```text
3,5,10 + 6,8,12
```

Track classification:

- Vehicle purchase = Essential.
- Loan = Modifier.
- Commercial = Modifier.
- Condition/quality = Outcome.
- Theft/recovery = Negative Risk / Recovery Track.
- Sale = Essential if asked.

---

### 3.5 Travel / Foreign

Travel houses:

```text
3,9,12
```

Meanings:

- 3 = away from home, short travel, away from motherland.
- 9 = long journey, pilgrimage, foreign travel.
- 12 = settling abroad, place away from motherland, long journeys.
- 7 = change in course of journey.

Foreign travel:

```text
3,9,12 with separative planets Sun, Saturn, Rahu, Ketu
```

Settling abroad:

```text
Majority of planets signify 3,9,12 and only one or two planets signify 2,4,11.
```

Return to motherland:

```text
2,4,11
```

Purpose of travel:

| Purpose | Combination |
|---|---|
| Studies | 2,4,5,9,11 |
| Job | 2,6,10,11 |
| Business | 2,7,10,11 |
| Tourism | 5 |
| Marriage | 2,7,11 |
| Medical emergency | 1,6,8,12 with benefics in DBA |
| Conference | 3,11 |
| Sports | 5,11 + Sun |
| Prizes | 6,11 + Venus/Jupiter |
| Awards | 10,11 + Venus/Jupiter |
| Pilgrimage | 3,12 or 9,12 with Jupiter/Venus |

Delay in return:

| Cause | Combination |
|---|---|
| Sickness | 1,6,8 with 3,9,12 |
| Change of course | 7 with 3,9,12 |
| Extension of stay | continued 3,9,12 |
| Litigation | litigation combination with 3,9,12 |
| Death | requires longevity rules; do not predict death without longevity module |

Foreign-domain resolver:

If user says “abroad,” classify:

1. physical travel,
2. temporary stay,
3. permanent settlement,
4. foreign employer/client,
5. foreign income,
6. remote foreign work,
7. visa/legal permission.

Do not merge these.

Track classification:

- Physical travel = Essential if travel/relocate/move/live abroad is asked.
- Foreign job/company/client = Modifier unless physical relocation is explicit.
- Foreign settlement = Essential only for settle/live/relocate/PR style questions.
- Return home = Separate Event Track.
- Purpose = Modifier/Outcome.

---

### 3.6 Career / Service / Business

Service/job:

```text
2,6,10,11
```

Business:

```text
2,7,10,11
```

Meanings:

- 2 = accumulated wealth, money, bank accounts.
- 6 = service, work conditions.
- 7 = business, trade, commerce, partner.
- 10 = career, name, fame, status.
- 11 = gain, increments, promotion, fulfillment.

Job success hierarchy:

```text
2,6,10,11 = 6,10,11 = 6,11 = 10,11 > 2,11 = 11 > 2,6,10 = 6,10 > 6 = 10 > 2
```

6,11 = strong competitive success / money.

10,11 = status / authority.

2,11 = wealth increase, weaker than 6,11 or 10,11.

Government job:

```text
Sun or Moon DBA involvement
```

Corporate/public sector:

```text
Jupiter, Mercury, Venus involvement
```

Small establishment:

```text
Rahu, Ketu, Saturn involvement
```

Written test:

```text
6,11
10,11
4,9,11
5,11
4,11
```

Interview/group discussion:

```text
3,6,11
3,10,11
3,11
```

No job / career obstacle:

```text
5,8,12
6,8,12
```

Change in career:

```text
5,9 with separative planets Sun, Saturn, Rahu, Ketu
```

Good change:

```text
Change track + 2,6,10,11 or 2,7,10,11
```

Bad change:

```text
Change track + 5,8,12 or 6,8,12
```

Job change / resignation:

- Track 1: current job continuation = 2,6,10,11.
- Track 2: separation/change = 5,9 or separative factor if supplied.
- Track 3: new job = 2,6,10,11.

Do not advise leaving unless replacement/gain track supports.

Business router:

| Business type | Combination |
|---|---|
| Solo business | 1,2,10,11 |
| Partnership business | 2,7,10,11 |
| Client/service business | 6,7,10,11 |
| Investment/speculation business | 2,5,8,11 |
| Loan-funded business | 2,6,10,11 |

Track classification:

- Job/service = Essential.
- Business = Essential if asked.
- Promotion/status = Outcome.
- Income = Outcome.
- Interview/test = Process.
- Career change = Transition Track.
- Job loss = Negative Risk.

---

### 3.7 Health / Disease

Disease houses:

```text
1,6,8,12
```

Meanings:

- 1 = body/self.
- 6 = sickness/disease.
- 8 = chronic disease, surgery, obstruction.
- 12 = bed confinement, hospitalization, expense.

Small disease:

```text
1,6
```

Long disease / surgery:

```text
1,6,8 especially with Mars/Ketu
```

Incurable or long medical dependence:

```text
1,6,8,12
```

Ineffective treatment:

```text
1,4,10
```

Good health / cure:

```text
5,11
```

Recovery facilitator:

```text
9
```

Recovery:

```text
5,11 or 9
```

Accident:

```text
1,4,8,12 with natural malefics
```

Accident with injury:

```text
1,4,6,8,12
```

Accident injury body part:

Use repeated houses in the accident combination to identify affected body areas.

Health limitation:

For medical questions, do not replace professional medical advice. State that this is astrology-based interpretation only.

Track classification:

- Disease presence = Essential.
- Recovery = Outcome.
- Surgery = Process.
- Hospitalization = Modifier.
- Accident = Separate Event Track.
- Medical danger = Negative Risk.

---

### 3.8 Marriage / Relationship

Marriage:

```text
2,7,11
```

Meanings:

- 2 = family/addition to family.
- 7 = spouse/marriage/partnership.
- 11 = fulfillment of desire.

Use exact KP rule if available. Principal cusp may be 7th or 11th depending query and packet rule.

Existing relationship / romance:

```text
5,7,11
```

Romance turning into marriage:

- Track 1: relationship/romance = 5,7,11.
- Track 2: marriage = 2,7,11.

Marriage requires marriage track support.

Happy married life / good conduct toward spouse:

```text
2,7,11,5,9 repeated in majority of planets
```

Unhappy married life / bad conduct:

```text
1,6,10,8,12 repeated in majority of planets
```

Aggression/bickering:

```text
7,8,12
or
6,8,12
especially with Mars/Pluto if packet supports
```

Separative tendencies:

```text
1,6,10
1,4,10 for dry/non-caring nature
```

Divorce/separation:

Use supplied KP/Nadi marriage denial rules. Default obstruction may include 6 as 12th from 7th only when marriage separation logic is active. Do not invent divorce from 6 alone.

Second marriage:

Requires specific dual/re-marriage rules from packet or supplied extract. If missing, mark second-marriage rule missing.

Foreign spouse:

```text
Marriage Track + Foreign Modifier Track
```

Childbirth after marriage:

Run Child Track separately.

Track classification:

- Marriage = Essential.
- Romance = Existing-condition Track.
- Foreign spouse = Modifier.
- Happiness/stability = Outcome.
- Divorce/separation = Negative Risk / Separate Event Track.
- Children = Separate Event Track.

---

### 3.9 Children

Childbirth:

```text
2,5,11
```

Meanings:

- 2 = addition to family.
- 5 = children/conception.
- 11 = fulfillment/gain.

Conception difficulty / denial:

```text
1,4,10 where child rule applies
```

4th as 12th from 5th:

May deny children when active by event rule.

Abortions/miscarriages:

```text
8,12 with child combinations, especially if repeated
```

For female chart:

Childbirth combination is especially important because pregnancy and birth occur through her body.

Track classification:

- Childbirth = Essential.
- Conception = Process.
- Pregnancy continuation = Process/Outcome.
- Miscarriage risk = Negative Risk.
- Number/quality of children = Outcome.

---

### 3.10 Finance / Profit / Money

Money received / wealth:

```text
2,11
```

Professional income:

```text
2,6,10,11
```

Business profit:

```text
2,7,10,11
```

Profit from sale:

```text
Sale combination + 11
```

Loss:

```text
12 with relevant event
8,12 when obstruction/loss is event-specific
6,8,12 for serious obstruction, litigation, debt, or loss depending event
```

Loan:

```text
6 with money/property/vehicle/business track
```

Debt repayment:

```text
2,6,11
```

Insurance/provident/inheritance source:

```text
8 with gain/purchase combination
```

Track classification:

- Money = Outcome unless money itself is the main question.
- Loan = Modifier/Process.
- Profit = Outcome.
- Loss = Negative Outcome/Risk.
