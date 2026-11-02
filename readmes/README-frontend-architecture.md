# Frontend Architecture — React + Material UI + Tailwind CSS + TanStack Query

**Status:** Frontend architecture finalized.  
**Scope:** Frontend application structure, server-state management, authentication-state boundary, cache lifecycle, data fetching, mutations, styling integration, and frontend implementation guidance.

This document records the finalized frontend architecture decisions for the Urban Vault ticketing assignment. Claude Code must follow these decisions and must not independently substitute libraries or move responsibilities between layers without an explicit architecture change.

Frontend test tooling and required user-interaction scenarios are defined in `README-testing-strategy.md`; use Vitest, React Testing Library, `user-event`, and jsdom as specified there.

## 1. Core principle

The frontend owns presentation and user interaction. The Django backend remains authoritative for business rules, ticket workflow, permissions, validation, and data integrity.

- Do not reproduce backend authorization as if frontend checks were security controls.
- Frontend role checks and `available_actions` flags are only for rendering the right UI. Every action endpoint must independently enforce permission and state-transition rules.
- Do not keep duplicate copies of the same server data in React Context, component state, and TanStack Query.

## 2. Finalized server-state decision: TanStack Query

Use **TanStack Query for React (`@tanstack/react-query`), current v5 API** as the server-state management library.

This is the selected option after considering SWR, RTK Query, React Router loaders/actions, and custom hooks using Context/`useEffect`.

### Why this was selected

The application has several related API-backed views:

- Paginated ticket lists with server-side search, filters, tabs, and sorting;
- Ticket details;
- Reference data such as Clients, Offices, Floors, Departments, Issues, and eligible Workers;
- Ticket Activity, assignment/department History, and Comments;
- Mutations for ticket creation, Worker assignment, Department forwarding, Worker assessment, Mark Resolved, and comments.

A successful mutation can make several cached views stale at once. TanStack Query provides query-key-based caching, mutation handling, targeted invalidation, background refetching, and paginated-query support. This avoids implementing a bespoke server-data cache and synchronization layer.

### Why not Context API for all server data

React Context is suitable for values that must be available across the component tree, such as the authenticated session. It does not by itself provide a server-state lifecycle: query caching, request deduplication, stale-data handling, pagination cache, mutation invalidation, or background refetching. Rebuilding these behaviours with Context, `useEffect`, and custom hooks would add application code without improving this assignment.

Context remains useful for authentication state; it is not a replacement for TanStack Query in this design.

### Why not add Redux / RTK Query

Do not add Redux solely to obtain RTK Query. TanStack Query is already selected and does not require Redux. Avoid maintaining two server-state/cache systems.

## 3. State ownership boundaries

Use each mechanism for one clearly defined category of state:

| State category | Owner | Examples |
|---|---|---|
| Server/API state | TanStack Query | Tickets, ticket details, reference data, comments, activity, history, eligible Workers |
| Authentication/session state | React Context | In-memory access token, current authenticated user/profile, auth bootstrap/loading state, login/logout/account-switch actions |
| URL/navigation state | React Router Declarative mode with `useSearchParams` | Ticket tab, page, search, sort, applied filters |
| Local presentation state | `useState` / `useReducer` | Open dialog, expanded action panel, temporary UI toggles, unsaved local selection not managed by a form |
| Form state | React Hook Form + Zod | Ticket creation, assign Worker, change Department, assessment, comments |

Do not copy ticket lists or ticket-detail API responses into Context. Do not use Context as a global cache for Clients, Offices, Floors, Issues, or Departments.

The authenticated user's small session profile may be held in Auth Context because it is part of the active login session and is used for navigation/role-aware rendering. Do not create separate copies of that profile in unrelated global stores.

## 4. Provider and QueryClient setup

Create one stable `QueryClient` for the application and mount one `QueryClientProvider` near the application root. Do not create a new QueryClient on every render.

Use a central query-client configuration module. Keep the configuration modest and intentional; do not introduce persistence plugins, cross-tab cache broadcasting, or advanced cache infrastructure for this assignment.

### Cache isolation across accounts

This application supports switching between seeded accounts with different ticket visibility. User-specific cached data must never leak from one account to another.

On logout, account switch, or terminal authentication failure:

1. Clear the in-memory access token and current-user session state.
2. Clear the TanStack Query cache (`queryClient.clear()`).
3. Clear any user-specific local UI state.
4. Complete the next login/bootstrap flow for the newly authenticated account.

Do not persist ticket queries or user-specific query data in localStorage/sessionStorage. The JWT design already keeps the access token in memory and the refresh token in an HttpOnly cookie; server-state cache should also remain in memory for this assignment.

## 5. Query-key conventions

All query functions must include every variable that changes the requested data in the query key. Use stable, serializable query keys and centralize them in query-key factory modules. The key must distinguish different pages, filters, searches, tabs, sort orders, resource IDs, and Activity filters.

Suggested convention (exact module names can be adjusted without changing the semantics):

```ts
export const ticketKeys = {
  all: ["tickets"] as const,
  lists: () => [...ticketKeys.all, "list"] as const,
  list: (params: TicketListParams) =>
    [...ticketKeys.lists(), params] as const,
  details: () => [...ticketKeys.all, "detail"] as const,
  detail: (ticketId: number) =>
    [...ticketKeys.details(), ticketId] as const,
  activities: (ticketId: number, type: ActivityFilter) =>
    [...ticketKeys.all, ticketId, "activities", type] as const,
  history: (ticketId: number) =>
    [...ticketKeys.all, ticketId, "history"] as const,
  eligibleWorkers: (ticketId: number) =>
    [...ticketKeys.all, ticketId, "eligible-workers"] as const,
  filterOptions: () => [...ticketKeys.all, "filter-options"] as const,
};
```

Reference-data keys should include parent IDs and search/filter values, for example:

- `['clients', 'me']`
- `['clients', clientId, 'offices']`
- `['client-offices', officeId, 'floors']`
- `['issues', { search, departmentId }]`
- `['departments']`
- `['tickets', ticketId, 'eligible-workers']`

Do not put bearer tokens, refresh tokens, passwords, or other secrets in query keys.

## 6. Ticket list queries and server-side pagination

The backend remains responsible for filtering, searching, sorting, and pagination. React must not fetch all tickets and filter them locally.

Use a query key that contains the complete normalized list parameter object:

```ts
const ticketListQuery = useQuery({
  queryKey: ticketKeys.list(params),
  queryFn: () => getTickets(params),
  placeholderData: keepPreviousData,
});
```

The exact `params` object should include the current tab, page, page size, search text, Client filter, current Department filter, Facility Manager filter, workflow-stage filter, and ordering when those values are active.

For page transitions, `placeholderData: keepPreviousData` can keep the last page visible while the next page loads. Use `isPlaceholderData`/`isFetching` to show that the visible rows are being retained temporarily; do not misrepresent the old records as the completed new page. Disable navigation that depends on the not-yet-received page response while placeholder data is being shown.

The list's source of truth is the server response. Do not locally derive a new page by slicing the current page's records.

## 7. Dependent reference-data queries

Use TanStack Query for reference-data fetching and caching.

Examples:

- Fetch the current user's Clients.
- Fetch a selected Client's Offices.
- Fetch a selected Office's Floors.
- Search Issues and optionally restrict the search to the Department of the first selected Issue.
- Fetch the top four Quick Issues for the selected Client.
- Fetch eligible Workers for a specific ticket from the ticket-scoped endpoint.

Use dependent queries (`enabled` or equivalent) so an Office query does not run before a Client is selected, and a Floor query does not run before an Office is selected. When a parent selection changes, clear dependent form selections and ensure the query key changes to the new parent ID.

Treat the backend response as authoritative. The UI's dependent dropdowns are usability behaviour, not an authorization boundary.

## 8. Mutations and cache invalidation

Use `useMutation` for business actions. A mutation function calls the explicit action API; it must not update ticket workflow fields through a generic PATCH request.

After a successful mutation, invalidate the affected query families so active views refetch from the backend. Prefer targeted invalidation over clearing the entire cache, except on logout/account switch.

| Mutation | Queries to invalidate after success |
|---|---|
| Create Ticket | Ticket lists; Ticket filter options; selected Client's Quick Issues (the new ticket changes frequency/ranking); optionally the created Ticket detail if navigated to it |
| Assign Worker | Ticket detail; all relevant Ticket lists; Ticket Activity; Ticket History; eligible-Workers query if needed |
| Change Department | Ticket detail; Ticket lists; Ticket filter options; Ticket Activity; Ticket History; eligible-Workers query |
| Submit Assessment | Ticket detail; Ticket lists; Ticket Activity; Ticket History/assessment data |
| Mark Resolved | Ticket detail; Ticket lists (ticket moves from Open to Closed); Ticket Activity; Ticket History if assignment end is shown |
| Add Comment | Ticket Activity (and any comment-only view if implemented) |

If a mutation response includes a complete updated Ticket representation, it may be used to update the exact detail cache, but still invalidate any list/activity/history views whose data or ordering may have changed. Do not optimistically update workflow transitions unless rollback and conflict behaviour are implemented correctly; a normal mutation followed by targeted invalidation is preferred for this assignment.

The backend can return `400`, `401`, `403`, `404`, and `409` responses. Display field validation errors and business conflicts clearly. Do not convert a failed mutation into a success-looking optimistic state.

## 9. Query retries, stale data, and refetching

TanStack Query v5 has configurable defaults for staleness, retries, background refetching, and garbage collection. Do not blindly depend on defaults without understanding them.

Recommended application policy:

- Configure `staleTime` intentionally by resource. Reference/catalog data can be cached longer than ticket workflow data.
- Ticket lists and ticket details should not be treated as permanently fresh; use targeted invalidation after actions.
- Avoid polling unless a specific product requirement is added. Real-time ticket updates are not required by this assignment.
- Configure query retry behaviour so authentication and business errors (`401`, `403`, `404`, `409`, and normal validation `400`) are not retried as transient failures. The Axios authentication interceptor handles a refresh attempt for an expired access token; it must not create infinite retry loops.
- A small bounded retry may be used for transient network errors or selected `5xx` responses.
- Do not automatically retry non-idempotent business mutations such as ticket creation, Worker assignment, Department forwarding, assessment submission, or comment creation. The backend may have processed the request even when the client lost the response; blind retry can duplicate an operation. Mutation retry should remain disabled unless an endpoint has an explicit idempotency contract.
- Use TanStack Query's cancellation signal where it is useful for rapidly changing search inputs so stale search requests do not overwrite the current result.

## 10. Interaction with JWT authentication

The authentication design is defined in `README-authentication.md` and remains authoritative:

- SimpleJWT on Django;
- Access token in React memory;
- Refresh token in an HttpOnly cookie;
- Access-token refresh is coordinated through the Axios client/interceptor;
- A single in-flight refresh operation is shared by concurrent failed requests;
- On logout/account switch, clear the QueryClient cache and authentication state;
- On startup, call `GET /api/v1/auth/csrf/` and send the returned token in `X-CSRFToken` on login, refresh, and logout requests.

Do not put access or refresh tokens in TanStack Query cache data, query keys, persisted browser storage, or URLs.

TanStack Query does not replace the authentication provider. It handles server data after the API client has attached a valid access token.

## 11. Feature-based frontend organization

Use feature-oriented folders so a feature's API functions, query hooks, components, pages, schemas, and types can be found together.

Suggested structure:

```text
frontend/src/
  app/
    App.tsx
    router.tsx
    providers/
      AppProviders.tsx
      queryClient.ts
  features/
    auth/
      api/
      components/
      context/
      hooks/
      pages/
      types/
    tickets/
      api/
      components/
      hooks/
      pages/
      schemas/
      types/
    reference-data/
      api/
      hooks/
      types/
  shared/
    api/
      axiosClient.ts
    components/
    hooks/
    layouts/
    theme/
    utils/
  main.tsx
```

This structure is a guide, not a reason to create empty directories or over-abstract every component. Keep implementation proportionate to the assignment.

## 12. Material UI and Tailwind CSS

The assignment requires React and Material UI for core UI elements. The project will combine Material UI with Tailwind CSS:

- Material UI: core interactive/application components such as Buttons, TextFields, Autocomplete, Select, Dialogs, Tabs, Tables, Pagination, Snackbars, and other form controls.
- Tailwind CSS: page layout, flex/grid, spacing, responsive breakpoints, and lightweight utility styling.
- MUI theme: consistent component colours, typography, shape, and component defaults.

Avoid styling the same property in conflicting ways through Tailwind classes and MUI `sx` props. Prefer one clear owner for each styling concern.

For a Vite/SPA application using Tailwind CSS v4, follow the current official MUI integration guidance:

1. Use `StyledEngineProvider` with `enableCssLayer`.
2. Set CSS layer order so MUI styles precede Tailwind utilities:

```tsx
import { StyledEngineProvider } from "@mui/material/styles";
import GlobalStyles from "@mui/material/GlobalStyles";

<StyledEngineProvider enableCssLayer>
  <GlobalStyles styles="@layer theme, base, mui, components, utilities;" />
  <App />
</StyledEngineProvider>
```

The Tailwind global stylesheet must use the matching layer order before importing Tailwind as shown in the official integration guide. Verify the exact setup against the installed MUI and Tailwind major versions; do not mix the Tailwind v3 integration recipe with v4.

## 13. Finalized supporting frontend choices

All choices in this section have been explicitly approved and are part of the implementation specification.

| Area | Finalized choice | Responsibility / constraint |
|---|---|---|
| Framework/build | React + TypeScript + Vite | Single-page React application; use TypeScript for application code and API contracts. |
| UI components | Material UI | Use for core interactive/application controls, as required by the assignment. |
| Styling | Tailwind CSS v4 + Material UI | Tailwind for layout, spacing, responsive utilities, and lightweight styling; MUI for core components and theme. Use the official CSS-layer integration in Section 12. |
| Routing | React Router, Declarative mode | Navigation and route protection only; do not use route loaders/actions as a second server-state layer. |
| Authentication state | React Context | Own current-user/session state and in-memory access token; do not store ticket/reference-data API responses here. |
| Local UI state | React `useState` / `useReducer` | Own temporary component-level presentation state. |
| URL state | React Router `useSearchParams` | Own ticket tab, page, page size, search, applied filters, and ordering. |
| Forms | React Hook Form | Own form values, submission lifecycle, touched/dirty state, and field-level errors. Use `Controller` for controlled MUI components where needed. |
| Form validation | Zod + `@hookform/resolvers` | Define client-side schemas and infer TypeScript types. Django remains authoritative for business validation and authorization. |
| HTTP client | Axios | Central API client, Bearer access-token attachment, refresh-cookie request, response handling, and centralized error normalization. |
| Refresh concurrency | Single-flight refresh in Axios interceptors | Concurrent 401 responses share one refresh request; retry each eligible original request at most once. See `README-authentication.md`. |
| Frontend tests | Vitest + React Testing Library + jsdom | Unit/component and user-interaction tests in the Vite project. |
| Redux | Not used | Do not add Redux/RTK Query; TanStack Query is the selected server-state library. |

### React Router responsibility boundary

Use React Router in Declarative mode. It owns routes, navigation, route parameters, protected-route presentation, and URL search parameters. Use `useSearchParams` for ticket listing state so refresh, deep links, and browser Back/Forward preserve the selected tab, page, search, filters, and ordering. Reset `page` to 1 when search or applied filters change.

Do not introduce React Router Data APIs (loaders/actions) for ticket or reference-data fetching. TanStack Query remains the single owner of API-backed server state. Route components call feature query hooks; the query keys include the normalized URL parameters.

### React Hook Form and Zod responsibility boundary

Use React Hook Form for all forms: ticket creation, Worker assignment, Department forwarding, Worker assessment, and comments. Use Zod schemas with `zodResolver` for immediate client-side validation. Use `Controller` when integrating controlled MUI fields such as Autocomplete.

Role-aware form validation may make Description optional for Client users and required for Facility Manager / Department POC users. Conditional Office and Floor fields must follow the finalized ticket-creation and reference-data READMEs. The frontend must not treat Zod validation as a security boundary; Django must repeat all business-critical validation.

### Axios and JWT responsibility boundary

Use one configured Axios instance for API calls. The request interceptor adds the current in-memory access token as `Authorization: Bearer <token>` to protected API requests. The refresh request sends the HttpOnly refresh cookie using `withCredentials: true` and includes the required CSRF protection described in `README-authentication.md`.

Implement a single-flight refresh mechanism: when multiple requests fail with an expired access token, they await the same in-flight refresh operation rather than rotating the refresh cookie concurrently. Retry each original request no more than once. Exclude login, refresh, and logout endpoints from recursive refresh handling. If refresh fails, clear the access token, clear the TanStack Query cache and return the user to the login flow.

Do not store access tokens or refresh tokens in localStorage, sessionStorage, query keys, URLs, or persisted query caches. Do not log tokens or credentials.

### Vitest and React Testing Library responsibility boundary

Use Vitest as the test runner, jsdom as the DOM environment, and React Testing Library for tests expressed through user-visible behaviour. Use `user-event` for realistic interactions where appropriate. Test at least an important ticket-creation interaction and role-specific ticket action visibility; the overall assignment also requires backend/API, authorization, and Celery tests documented in the testing plan.

Do not test implementation details such as internal component state or hook call counts unless there is a specific reason. Mock API boundaries where appropriate, but retain integration coverage for important form and query interactions.

### No duplicate server-state layer

Do not implement a custom Context-based API cache, Redux store, or React Router loader cache. TanStack Query remains the one server-state cache. Context is limited to authentication/session information.

## 14. Frontend behaviour requirements

The frontend must support:

- All four user roles, while relying on backend authorization for actual access;
- Open and Closed Ticket tabs;
- Server-driven pagination, search, filters, and sorting;
- Conditional Client, Client Office, Floor, Issue, and Worker controls;
- Loading, empty, success, validation, permission, not-found, conflict, and unexpected-error states;
- Preventing duplicate form submissions while a mutation is pending;
- Responsive desktop and mobile layouts;
- Semantic HTML, accessible labels, keyboard-operable controls, and visible focus states;
- Refreshing affected cached data after successful business mutations;
- Clearing user-specific cache data when accounts change.

### Screens and routes (Phase 0 audit, G6)

| Route | Screen | Notes |
|---|---|---|
| `/login` | Login | Email and password; a development-only demo-account picker pre-fills a seeded email (`README-authentication.md` §8) |
| `/tickets` | Ticket list | Open/Closed tabs, search, Filters, Sort, pagination, all held in URL search params; "Create New Ticket" for roles that can create |
| `/tickets/new` | Create Ticket | One form with Client and internal-employee variants (`README-ticket-creation-api.md`) |
| `/tickets/:ticketId` | Ticket detail | Header, role CTA panel, Issue Description, Activity, comment box |
| `*` | Not found | Link back to the ticket list |

Unauthenticated users are redirected to `/login`; `/` redirects to `/tickets`.

Wireframe details to reproduce:

- **Ticket card:** Issue names; `{Office}; {Floors}` ("All Floors" when the Ticket has no Floor rows); `#TKT-{id}`; workflow-stage label; red **Action Required** badge when `action_required` is true; Created timestamp and creator; Current Assignee(s) shown as a chain (POC › Worker); **View** button.
- **Detail layout:** the ticket header and the role's CTA panel stay sticky at the top; the "Write a comment / Post" box stays sticky at the bottom.
- **CTA panels** expand inline below their buttons: Assign Worker (Worker drop-down + Ok), Change Department (Department drop-down + required forwarding note + Ok), Submit Assessment (three radio options + Submit), Mark Resolved (confirmation + Submit).
- **Banner text**, word for word from the wireframe: "Ticket created successfully. If the issue is resolved, you can mark it as resolved." (creator, after creation); "A new ticket has been assigned to you. Review it and take the next action." (current POC); "You have been assigned this ticket. Take action." (current Worker); "If the issue no longer persists, you can mark it as resolved." (Mark Resolved panel).
- **Activity:** filter chips All / Actions / Comments, with **All selected by default**; "N events" shows the feed's `count`; each action shows actor, verb, timestamp, and the inline History (`from → to`) from its `change` field; a Department change also shows its forwarding note.
- **People** are shown as "Name (Role label)" using `role_label` from the API.
- **Quick Issues:** chips from a different Department than an already-selected Issue are disabled.
- **Dates** are shown in the browser's local time, formatted like `27-Oct-2025 11:40 AM`.

## 15. Acceptance criteria for implementation

Claude Code must verify at least the following:

1. Ticket list query keys change when page, tab, page size, search, filters, or ordering changes.
2. The backend receives those values and performs all filtering/search/pagination; the frontend does not filter the current page as a substitute.
3. Ticket details, Activity, History, and reference data are fetched through query hooks rather than copied into a global Context store.
4. Creating or updating a ticket invalidates all affected query families listed in Section 8.
5. Switching from one seeded account to another clears previous account query data before the new account's data is displayed.
6. Multiple simultaneous expired-access-token responses do not cause multiple concurrent refresh-token rotations (see `README-authentication.md`).
7. Paginated query transitions use a clear pending/placeholder indicator and never label stale previous-page rows as the successfully loaded new page.
8. A failed state-changing mutation does not leave the UI displaying a successful transition.
9. No ticket or user-specific query data is persisted to localStorage/sessionStorage.
10. MUI and Tailwind v4 styles coexist using the documented CSS-layer integration.
11. React Router is used in Declarative mode; ticket listing parameters are read from and written to URL search parameters.
12. Ticket and reference-data fetching is implemented through TanStack Query hooks, not React Router loaders or Context `useEffect` caches.
13. Forms use React Hook Form with Zod resolvers; backend validation errors are mapped to visible field/form feedback.
14. Axios uses one configured client with Bearer-token attachment, HttpOnly refresh-cookie requests, CSRF handling, and single-flight refresh concurrency.
15. Each original request is retried at most once after refresh; login/refresh/logout requests cannot enter a recursive refresh loop.
16. Component tests run under Vitest + jsdom and use React Testing Library user-facing queries/interactions.

## 16. Out of scope

Do not add the following unless a later decision requires them:

- Redux solely for API caching;
- GraphQL or Apollo Client;
- A custom global server-state cache;
- Offline-first mutation persistence;
- Real-time WebSocket ticket updates;
- Automatic polling for ticket updates;
- Persistent localStorage caching of ticket data;
- Complex optimistic updates for workflow transitions.

## 17. Official references

Use the current official documentation when implementing library-specific APIs. The selected TanStack Query major is v5; do not copy v3/v4 examples without adapting them.

- [TanStack Query React v5 documentation](https://tanstack.com/query/latest/docs/framework/react/overview)
- [TanStack Query query keys](https://tanstack.com/query/latest/docs/framework/react/guides/query-keys)
- [TanStack Query paginated / lagged queries](https://tanstack.com/query/latest/docs/framework/react/guides/paginated-queries)
- [TanStack Query query invalidation](https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation)
- [TanStack Query invalidations from mutations](https://tanstack.com/query/latest/docs/framework/react/guides/invalidations-from-mutations)
- [TanStack Query important defaults](https://tanstack.com/query/latest/docs/framework/react/guides/important-defaults)
- [TanStack Query query cancellation](https://tanstack.com/query/latest/docs/framework/react/guides/query-cancellation)
- [Material UI Tailwind CSS v4 integration for Vite/SPAs](https://mui.com/material-ui/integrations/tailwindcss/tailwindcss-v4/)
