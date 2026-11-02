# Domain Model — Urban Vault Ticketing System

**Status:** FINALIZED  
**Purpose:** Define the business entities, user roles, and relationships that the application represents.

## 1. Product summary

Urban Vault needs a facility-management ticketing system. A Client or an eligible internal employee reports an issue at a specific Client Office. The ticket is routed to the Department associated with the selected issue. The Department POC coordinates the work by assigning a Worker or forwarding the ticket to another Department. The Worker submits one assessment. A Client user of the ticket's Client, or the user who created the ticket, can mark it resolved.

The product is centred on a ticket and its lifecycle—not on a generic CRUD interface.

## 2. User roles

The application has four authenticated roles. A user has one role.

| Role | Business responsibility |
|---|---|
| `CLIENT` | Reports problems for an associated Client organization; can view that Client's tickets and mark an authorized ticket resolved. |
| `FACILITY_MANAGER` | Oversees one or more Properties and can view tickets originating from Client Offices in those Properties. |
| `DEPARTMENT_POC` | Coordinates tickets currently assigned to their organization-wide Department. |
| `WORKER` | Performs the work for tickets assigned to them and submits the ticket assessment. |

Use one custom Django User model for all roles. Do not create a separate authentication table for each role.

## 3. Organization and physical-location model

### Client

A Client is an organization that uses a facility, such as Harness or Acme.

### Property

A Property is the physical building or premises managed by Urban Vault.

- Each Property has exactly one designated Facility Manager.
- One Facility Manager may manage multiple Properties.
- Facility Manager responsibility is assigned at Property level, not Client Office level.

### Client Office

A Client Office is a particular office/location occupied by a Client within a Property.

- One Client can have multiple Client Offices.
- One Property can contain multiple Client Offices.
- Each Client Office belongs to exactly one Client and one Property.
- A Client may occupy an entire Property, or multiple Clients may occupy different offices in the same Property.

Property and Client Office are distinct concepts even when one Client Office occupies an entire Property.

### Floor

A Floor is a physical floor within a Property.

- A Property contains multiple Floors.
- A Client Office can occupy multiple Floors.
- A physical Floor can be shared by multiple Client Offices.
- Model Client Office occupancy through a many-to-many relationship between `ClientOffice` and `Floor`.
- A Client Office may only be mapped to Floors belonging to its own Property. Validate this cross-table rule in the application.

The ticket stores the specific Floors affected by the issue, using a separate ticket-to-floor relationship.

## 4. Client membership

`User` and `Client` have a many-to-many relationship through `UserClient`.

- A User may be associated with multiple Clients.
- A Client may have multiple associated Users.
- This mapping applies to all four user roles, as agreed.
- Internal employees use this mapping to determine which Clients they may select when creating a ticket.
- A Client-role user's ticket visibility is based on their associated Clients.
- For internal roles, Client membership supports ticket creation but does not itself grant Client-level ticket visibility. Their ticket visibility follows their role-specific rule in `README-authorization.md`, plus the creator rule: every user can see the tickets they created.

When creating a ticket, show a Client selector only when the authenticated user has multiple associated Clients. If exactly one Client is associated, select it automatically.

After a Client is selected, show a Client Office selector only when that Client has multiple Client Offices. If exactly one Office exists, select it automatically. The selected Office is the location to which the Ticket belongs.

## 5. Departments and workforce

Departments are organization-wide. They are not scoped to Properties.

- Each Department has exactly one designated Department POC.
- A Department can have multiple Workers.
- Every Department has exactly one designated POC, represented by `Department.poc_user` (a one-to-one User relationship).
- Every Worker belongs to exactly one Department through a `DepartmentWorker` mapping row; `worker_id` is unique in that table.
- Department membership is not stored as `User.department_id`.
- A Worker is not mapped to a Property in this assignment.
- The Department POC is derived from the ticket's current Department; do not create a separate per-ticket POC assignment.

The designated POC must be a User with role `DEPARTMENT_POC`. The Department-to-POC relationship itself establishes which Department they represent. Validate the role and ensure every active POC account is designated for exactly one Department. Workers are mapped separately through `DepartmentWorker`, which has a unique `worker_id` and a foreign key to Department; ensure every active Worker account has exactly one mapping.

## 6. Issues and Department classification

An `Issue` is a selectable issue type such as `AC not cooling`, `Lights flickering`, or `Internet not working`.

- Each Issue belongs to exactly one Department.
- A Ticket can contain multiple Issues.
- All Issues selected for one Ticket must belong to the same Department.
- The Ticket's initial/origin Department is derived from the selected Issues at creation.
- The Ticket's current Department may later change through Department forwarding.

The same Issue can be selected on many Tickets. Use a many-to-many relationship through `TicketIssue`.

## 7. Ticket domain relationships

A Ticket:

- belongs to exactly one Client Office;
- is created by exactly one User;
- contains one or more Issues, all from the same Department;
- stores an immutable `origin_department_id`;
- stores a mutable `current_department_id`;
- may affect multiple Floors belonging to its Client Office;
- may have multiple assignment-history records, with at most one active Worker assignment;
- has at most one assessment in the assignment's defined workflow;
- has multiple Activity records and Comments.

The following relationships are derived and should not be redundantly stored on Ticket:

- Client: derive through `ticket.client_office.client`.
- Facility Manager: derive through `ticket.client_office.property.facility_manager`.
- Current Department POC: derive through `ticket.current_department.poc_user`.
- Current Worker: derive from the active `TicketAssignment`.

## 8. Relationship summary

| Relationship | Cardinality |
|---|---|
| Client → Client Office | One-to-many |
| Property → Client Office | One-to-many |
| Property → Floor | One-to-many |
| Client Office ↔ Floor | Many-to-many |
| User ↔ Client | Many-to-many |
| Property → designated Facility Manager | Many properties per manager; one manager per property |
| Department → designated POC | One-to-one through `Department.poc_user`; each POC can be designated for at most one Department |
| Department → Workers | One-to-many through `DepartmentWorker`; each Worker can belong to at most one Department |
| Department → Issue | One-to-many |
| Client Office → Ticket | One-to-many |
| Ticket ↔ Issue | Many-to-many, constrained to one Department per Ticket |
| Ticket ↔ Floor | Many-to-many, constrained to the Ticket's Client Office |
| Ticket → Assignment history | One-to-many |
| Ticket → Assessment | Zero-or-one in this assignment |
| Ticket → Activity / Comments | One-to-many |

## 9. Explicitly out of scope

Do not introduce these features as part of the current assignment:

- multi-tenant Urban Vault organizations;
- Property-specific Departments;
- multiple designated POCs per Department;
- Worker-to-Property eligibility mapping;
- multiple simultaneously active Workers on one Ticket;
- automatic Worker selection or workload balancing.

These may be future product extensions, but they are not part of the agreed assignment scope.
