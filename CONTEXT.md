# Bedashing network right-sizing

Decision support for deciding which Bedashing Beauty Lounge branches in Dubai to protect, hold or shrink, and where to grow.

## Language

### Network and geography

**Branch**:
An existing (or scenario-hypothetical) Bedashing location.
_Avoid_: store, site, outlet

**Community**:
One of the 50 official Dubai statistical communities, carrying a population figure.
_Avoid_: district, neighbourhood, area

**Opportunity area**:
A community evaluated as a place Bedashing could open a new branch.
_Avoid_: whitespace cell, candidate site, hex

**Catchment**:
The set of communities whose nearest branch (straight-line) is a given branch.
_Avoid_: service area, trade area, radius

**Competitor**:
A non-Bedashing beauty or hair salon that counts as part of the competitive set.
_Avoid_: rival, POI

### Overlap

**Cannibalisation**:
Overlap between two of Bedashing's own branches competing for the same communities.
_Avoid_: contested share, self-overlap, overlap (unqualified)

**Competitive overlap**:
A branch's catchment being shared with competitors.
_Avoid_: saturation (unless meaning per-capita density), overlap (unqualified)

### Decisions

**Branch action**:
PROTECT, HOLD or SHRINK, assigned to a branch.

**Opportunity action**:
GROW, WATCH or SKIP, assigned to an opportunity area.

### Audiences

The tool supports the conversation between these three roles.

**Portfolio team**:
Bedashing's network, real estate and expansion team and its analysts. The primary user: it uses the tool to form and defend recommendations.
_Avoid_: user, analyst (unqualified)

**Decision-maker**:
Bedashing's COO. Approves or questions the portfolio team's recommendations. Accountable for branch operations and return on invested capital.
_Avoid_: leadership, user

**Board**:
The PE owner's board and operating partner, who must be persuaded that a decision is defensible.
_Avoid_: investor, PE firm (as the user)
