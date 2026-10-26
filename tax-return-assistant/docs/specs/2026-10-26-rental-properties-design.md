# Rental properties: the firm's rental tab, ownership share and private use (26 Oct 2026)

The owner showed the firm's rental worksheet ("M25 Rental <property>"). Sawnx's M25 tab listed figures by category
but claimed 100% of everything, had one tab for all properties, and had no property details. This design makes the
workpaper match the firm's sheet and makes the return use the client's share.

## Decisions (owner, 26 Oct 2026)
- **Share and property details live on a property form in Sawnx** (a Rental page per client year). When a
  document shows the client's ownership share (e.g. 50%), the readers fill it in as a *suggestion*; the preparer can
  change it. Until a person saves it, a review note says the share was assumed or suggested.
- **Columns by document, changeable:** figures from the property manager's statement go to *Agent Summary*; figures
  from other papers to *Owners' Contribution*; any figure can be moved to *This Taxpayer's Contribution Only*.
- **One tab per property.** With one property everything goes to it; with two or more each rental document is
  assigned a property on the Rental page.
- **Private use apportionment is included:** ticked expense rows are reduced by the private use percentage.

## Privacy
The firm's sheet shows owner names and the street address. Sawnx's workpaper shows the client code, a short
property name the preparer types (default "Property 1"; never filled in by a reader), and share percentages. Owner
names and addresses are never stored, and no reader returns them (the AI's answer has only a number for the share).

## Data: `Work/<code>/FY<year>/rental.json` (through the output guard)
```
{"properties": [{"id": "P1", "name": "Property 1", "share": "50", "share_source": "person" | "suggested" | "default",
                 "share_doc": "D003", "private_use": "0", "weeks_rented": 52, "weeks_available": 52,
                 "first_income": "", "apportion": {"rent.agent_fees": false, ...}}],
 "documents": {"D003": "P1"},
 "columns": {"F0012": "taxpayer"}}
```
No file, or no properties: one default property (100%, 0% private use, 52/52 weeks, share_source "default").

## Rows (the firm's order and wording)
Income: A Rental Income (`rent.gross`), B Other Income (new `rent.other_income`, part of 21 P), C Total Income.
Expenses: D Advertising, E Body Corporate, F Borrowing Expenses, G Cleaning, H Council Rates, I Deductions for
Decline in Value, J Gardening/Lawnmowing, K Insurance, L Interest on Loans (21 Q), M Land Tax, N Legal Expenses,
O Pest Control, P Agent Fees, Q Repairs and Maintenance (each item on its own line, then a subtotal), R Capital Works
Deductions (21 F), S Office Supplies, T Travel Expenses, U Water Charges, V Sundry Rental Expenses (itemised),
W Total Expenses, X Net Income / (Loss). Every row shows, with "-" when empty, so the letters never move.

## Calculation (Python and the Excel formula are the same)
For each row: `ROUND(((agent + owners) × share + taxpayer_only) × (1 − private_use if apportioned else 1), 2)`.
Itemised rows (repairs, sundry) round each line, then add. Income rows are never apportioned. Apportioned by default:
every expense except Advertising and Agent Fees (as the firm's sheet); changeable per property.
Return labels per property: 21 P = C; 21 Q = L; 21 F = R; 21 U = W − L − R. The draft return adds them across
properties, so both tax calculations, the B01 Summary and Xero Tax entry use the client's share.

## Workpaper
- A tab per property, `M25 Rental <name>` (31 characters at most), in the firm's sections: Property Details
  (name, date first earned rental income, weeks rented, weeks available, private use %), Ownership (this taxpayer's
  share %; others' share as a formula), Income / Expenses (Apportion?, Agent Summary, Owners' Contribution, This
  Taxpayer's Contribution Only, letter, Taxpayer's Share, Prior Period, Sources), then the return labels with
  "Transferred to" links. Inputs are blue; shares are formulas of the inputs, so a reviewer can change the share
  or a tick in Excel and see the effect.
- Sources: each row lists its documents and pages, linked to the first.
- B01 Summary: each Item 21 label adds the property tabs' return-label cells.

## Readers
- The rental statement reader and the AI reader may report `ownership_share` (a percentage, 0–100) as a fact.
  On import (and Read again) Sawnx stores it as a suggestion for the document's property, unless a person already
  set the share; a different suggestion only adds a Things to check line.
- The AI schema gets `ownership_percent` (number or null) with the instruction to give only a number, never names.

## Checks
- **S18** (Medium): the rental share is assumed (100%) or only suggested by a reader; or, with two or more
  properties, a rental document isn't assigned to one (it's counted under the first). Confirm on the Rental page.
- S15–S17 and S7 work per figure as before.

## Sawnx
A **Rental** tab on the client year (shown when the year has rental figures or properties): each property's form
(name, share, private use, weeks, date first earned income, Apportion ticks), Add property, Remove property (only
when nothing is assigned to it), each rental document's property, and each rental figure's column. Changes are
audited (`rental_changed`, field names only).

## Not in this version
Acquisition and disposal details, the daily apportionment helper, prior-period amounts per row (the prior year is
only kept per return label), and reading weeks rented from documents.
