# Seed Data — Demo Accounts and Sample Records

**Status:** FINALIZED (Phase 0 audit decision G3)
**Command:** `python manage.py seed_demo_data`

The assignment requires seeded accounts for the Client, Facility Manager, Department POC, and Worker roles, and enough sample data to demonstrate pagination, search, filtering, and sorting. This document defines that data. The characters come from the wireframe.

## 1. Command behaviour

- **Deterministic:** the same input always produces the same records. Ticket attributes are generated from a fixed list or a fixed random seed, never from the current state of the database.
- **Idempotent:** running the command again does not create duplicates. Reference data and users are created with `update_or_create` on natural keys (email, names). Demo Tickets are created only when the database contains no Tickets; otherwise the command reports that Tickets already exist and skips them.
- **Password:** every demo account uses the password from the `SEED_DEMO_PASSWORD` environment variable. The command stops with a clear error if it is not set. No password is committed to the repository.
- **Never automatic:** containers do not run the command at startup; it is run explicitly (`README-infrastructure-deployment.md` §3.2).
- **No notifications:** seeded history is written directly, not through the ticket service functions, so no `NotificationOutbox` rows are created for historical data. Every seeded Ticket still gets the Issue, Floor, Assignment, Assessment, and Activity rows (with `change` metadata) that its state implies, and satisfies every database constraint.
- **Timestamps:** Ticket `created_at` values are spread over the 60 days before the seed date, so both sort directions and pagination are visible. Activity timestamps follow each Ticket's creation time in a realistic order.
- **Admin access:** not seeded. Use `python manage.py createsuperuser` when Django admin access is needed.

## 2. Organizations and locations

**Clients:** Harness, Acme.

**Properties:**

| Property | Designated Facility Manager | Floors |
|---|---|---|
| Koramangala Hub | Chandan S | 1F, 2F, 3F, 4F |
| HSR Layout Hub | Meera J | GF, 1F, 2F |

**Client Offices** (each demonstrates a different Floor rule):

| Office | Client | Property | Mapped Floors | Demonstrates |
|---|---|---|---|---|
| Harness-1317 | Harness | Koramangala Hub | 2F, 3F | Multi-Floor Office → Floor selector shown |
| HSR-1317 | Harness | HSR Layout Hub | none | No mapped Floors → no selector; card shows "All Floors" |
| Acme-0410 | Acme | Koramangala Hub | 4F | Single Floor → attached automatically |
| Acme-2201 | Acme | HSR Layout Hub | 1F, 2F | Multi-Floor Office in the second Property |

Harness has two Offices, so its users see the Office selector.

## 3. Departments, Issues, and Workers

| Department | Designated POC | Workers | Issues |
|---|---|---|---|
| Technical | Dhananjaya Murthy | Prakash Kumar, Ravi T | AC not cooling, Lift not working, Water leakage |
| IT | Abdul | Imran S | Internet not working, Wi-Fi slow, Printer not working |
| Housekeeping | Lakshmi N | Kavya P | Pantry not cleaned, Washroom not cleaned |
| Electrical | Suresh B | Manoj E | Lights flickering, Power outage |

The four wireframe Quick Issues (AC not cooling, Internet not working, Pantry not cleaned, Lights flickering) are the most frequent Issues in Harness's seeded history, so they appear as Harness's Quick Issues.

## 4. Demo accounts

All emails use the reserved `.test` domain. All passwords come from `SEED_DEMO_PASSWORD`.

| Email | Name | Role | Mappings | Demonstrates |
|---|---|---|---|---|
| `chaitanya.m@urbanvault.test` | Chaitanya M | CLIENT | Harness | Primary Client POC; Office selector (two Offices) |
| `priya.r@urbanvault.test` | Priya R | CLIENT | Harness, Acme | Client selector (two Clients) |
| `neha.k@urbanvault.test` | Neha K | CLIENT | Acme | Cross-Client isolation (cannot see Harness Tickets) |
| `chandan.s@urbanvault.test` | Chandan S | FACILITY_MANAGER | Harness, Acme; manages Koramangala Hub | Primary Facility Manager; Office list limited to Koramangala Hub (HSR-1317 excluded although Harness is mapped) |
| `meera.j@urbanvault.test` | Meera J | FACILITY_MANAGER | Harness, Acme; manages HSR Layout Hub | Second Property's manager |
| `dhananjaya.m@urbanvault.test` | Dhananjaya Murthy | DEPARTMENT_POC | Technical; Harness, Acme | Primary Department POC |
| `abdul@urbanvault.test` | Abdul | DEPARTMENT_POC | IT; Harness | Destination of forwarded Tickets |
| `lakshmi.n@urbanvault.test` | Lakshmi N | DEPARTMENT_POC | Housekeeping; Harness | |
| `suresh.b@urbanvault.test` | Suresh B | DEPARTMENT_POC | Electrical; Acme | |
| `prakash.k@urbanvault.test` | Prakash Kumar | WORKER | Technical | Primary Worker; current and historical assignments |
| `ravi.t@urbanvault.test` | Ravi T | WORKER | Technical | Second eligible Technical Worker |
| `imran.s@urbanvault.test` | Imran S | WORKER | IT | |
| `kavya.p@urbanvault.test` | Kavya P | WORKER | Housekeeping | |
| `manoj.e@urbanvault.test` | Manoj E | WORKER | Electrical | |

The login screen's development-only demo picker lists the four primary accounts first (Chaitanya M, Chandan S, Dhananjaya Murthy, Prakash Kumar), then the rest.

## 5. Tickets

Seed about **80 Tickets** across both Clients, all four Offices, and all four Departments, created by Client users, Facility Managers, and Department POCs.

The mix must cover every state and scenario:

| Scenario | Examples to include |
|---|---|
| `PENDING_TECHNICIAN_ASSIGNMENT`, `OPEN` | Fresh Tickets in every Department |
| `PENDING_TECHNICIAN_ASSESSMENT`, `OPEN` | Assigned to Prakash Kumar and to other Workers |
| `PENDING_DEPARTMENT_POC_REVIEW`, `TECHNICIAN_CLOSED` | All three assessment outcomes |
| `CLOSED` at each of the three stages | Resolved by a Client user, and by an internal creator (Facility Manager) |
| Forwarded | Technical → IT with a forwarding note; origin and current Department differ |
| Historical Worker | Closed Tickets whose assignment to Prakash Kumar has ended; Prakash keeps read-only visibility |
| Creator visibility | A Ticket created by Dhananjaya Murthy (Technical POC) with an IT Issue, so it routes to Abdul |
| Multiple Issues | Tickets with two Issues from the same Department |
| Comments | Comments from several roles, including after closure |

**Volume target:** each primary demo account (Chaitanya M, Chandan S, Dhananjaya Murthy, Prakash Kumar) sees **at least 12 Tickets in the Open tab and at least 12 in the Closed tab**. With the default page size of 10, every role sees at least two pages in each tab.

## 6. Acceptance checks

- Running the command twice leaves the record counts unchanged.
- Logging in as each primary account shows at least two pages in both tabs.
- Every filter (Client, current Department, Facility Manager, workflow stage) and the Issue search return a non-empty, correctly narrowed result for at least one primary account.
- Neha K cannot see any Harness Ticket.
- Chandan S's Office choices for Harness contain only Harness-1317.
