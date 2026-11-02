import { act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "../../../test/renderWithProviders";
import { buildTicketDetail } from "../../../test/factories";
import * as referenceDataApi from "../../reference-data/api/referenceDataApi";
import type { ClientOffice, Issue, QuickIssue } from "../../reference-data/types/referenceData.types";
import * as ticketsApi from "../api/ticketsApi";
import { TicketForm } from "./TicketForm";

const technicalDepartment = { id: 1, name: "Technical" };
const itDepartment = { id: 2, name: "IT" };

const harnessMainOffice: ClientOffice = {
  id: 10,
  name: "Harness-1317",
  code: "1317",
  property: { id: 5, name: "Koramangala Hub" },
  floor_count: 2,
};
const harnessHsrOffice: ClientOffice = {
  id: 11,
  name: "HSR-1317",
  code: "1317",
  property: { id: 6, name: "HSR Layout Hub" },
  floor_count: 0,
};
const acmeOffice: ClientOffice = {
  id: 20,
  name: "Acme-0410",
  code: "0410",
  property: { id: 5, name: "Koramangala Hub" },
  floor_count: 1,
};

const acNotCooling: Issue = { id: 101, name: "AC not cooling", department: technicalDepartment };
const liftNotWorking: Issue = { id: 102, name: "Lift not working", department: technicalDepartment };
const internetNotWorking: Issue = { id: 201, name: "Internet not working", department: itDepartment };

const harnessQuickIssues: QuickIssue[] = [
  { id: 101, name: "AC not cooling", department_id: 1, occurrences: 12, last_reported_at: "2025-10-27T06:10:00Z" },
  { id: 201, name: "Internet not working", department_id: 2, occurrences: 9, last_reported_at: "2025-10-26T06:10:00Z" },
];

function mockReferenceData() {
  vi.spyOn(referenceDataApi, "getMyClients").mockResolvedValue([
    { id: 1, name: "Harness" },
    { id: 2, name: "Acme" },
  ]);
  vi.spyOn(referenceDataApi, "getClientOffices").mockImplementation(async (clientId) =>
    clientId === 1 ? [harnessMainOffice, harnessHsrOffice] : [acmeOffice],
  );
  vi.spyOn(referenceDataApi, "getOfficeFloors").mockImplementation(async (officeId) => {
    if (officeId === harnessMainOffice.id) {
      return [
        { id: 102, name: "2F" },
        { id: 103, name: "3F" },
      ];
    }
    return officeId === acmeOffice.id ? [{ id: 104, name: "4F" }] : [];
  });
  vi.spyOn(referenceDataApi, "getQuickIssues").mockResolvedValue(harnessQuickIssues);
  // Mirrors the API: results are limited to a Department when one is given.
  vi.spyOn(referenceDataApi, "searchIssues").mockImplementation(async ({ departmentId }) =>
    [acNotCooling, liftNotWorking, internetNotWorking].filter(
      (issue) => departmentId === null || issue.department.id === departmentId,
    ),
  );
}

async function chooseOption(fieldName: string, optionName: string) {
  await userEvent.click(await screen.findByRole("combobox", { name: fieldName }));
  await userEvent.click(await screen.findByRole("option", { name: optionName }));
}

async function chooseIssue(issueName: string) {
  await userEvent.click(await screen.findByRole("combobox", { name: /Issue\(s\)/ }));
  await userEvent.click(await screen.findByRole("option", { name: issueName }));
}

function renderForm(role: "CLIENT" | "FACILITY_MANAGER" | "DEPARTMENT_POC" = "CLIENT") {
  const onCreated = vi.fn();
  renderWithProviders(<TicketForm role={role} onCreated={onCreated} onCancel={vi.fn()} />);
  return { onCreated };
}

describe("TicketForm", () => {
  beforeEach(() => {
    mockReferenceData();
  });

  it("filters Client choices by typed text and selects one with the keyboard", async () => {
    renderForm();
    const clientInput = await screen.findByRole("combobox", { name: "Client" });

    await userEvent.type(clientInput, "acm");

    expect(await screen.findByRole("option", { name: "Acme" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Harness" })).not.toBeInTheDocument();
    await userEvent.keyboard("{ArrowDown}{Enter}{Tab}");
    expect(await screen.findByText("Office: Acme-0410")).toBeInTheDocument();
  });

  it("shows Quick Issues loading feedback while the request is pending", async () => {
    vi.spyOn(referenceDataApi, "getQuickIssues").mockReturnValue(new Promise(() => {}));
    renderForm();
    await chooseOption("Client", "Acme");

    expect(await screen.findByRole("progressbar", { name: "Loading quick issues" })).toBeInTheDocument();
  });

  it("shows a Quick Issues error and retries without blocking ordinary Issue selection", async () => {
    vi.spyOn(referenceDataApi, "getQuickIssues")
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValue(harnessQuickIssues);
    renderForm();
    await chooseOption("Client", "Acme");

    expect(await screen.findByText("Could not load quick issues.")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /Issue\(s\)/ })).toBeEnabled();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("group", { name: "Quick Issues - tap to autofill" })).toBeInTheDocument();
    expect(screen.queryByText("Could not load quick issues.")).not.toBeInTheDocument();
  });

  it("does not submit a second ticket while creation is pending", async () => {
    let finishCreation!: (ticket: ReturnType<typeof buildTicketDetail>) => void;
    const createTicket = vi.spyOn(ticketsApi, "createTicket").mockReturnValue(
      new Promise((resolve) => { finishCreation = resolve; }),
    );
    renderForm();
    await chooseOption("Client", "Acme");
    await chooseIssue("AC not cooling");
    await userEvent.dblClick(screen.getByRole("button", { name: "Submit" }));

    expect(await screen.findByRole("button", { name: "Submitting…" })).toBeDisabled();
    expect(createTicket).toHaveBeenCalledTimes(1);
    await act(async () => finishCreation(buildTicketDetail()));
  });

  it("allows a corrected retry after a failed ticket submission", async () => {
    const createTicket = vi.spyOn(ticketsApi, "createTicket")
      .mockRejectedValueOnce(new Error("unavailable"))
      .mockResolvedValue(buildTicketDetail());
    const { onCreated } = renderForm();
    await chooseOption("Client", "Acme");
    await chooseIssue("AC not cooling");
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));
    await screen.findByRole("alert");

    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    expect(createTicket).toHaveBeenCalledTimes(2);
    expect(onCreated).toHaveBeenCalledOnce();
  });

  it("walks through Client, Office, Floors, and Issues, then submits the matching payload", async () => {
    const createTicket = vi.spyOn(ticketsApi, "createTicket").mockResolvedValue(buildTicketDetail({ id: 77 }));
    const { onCreated } = renderForm("CLIENT");

    // The user has two Clients, so a Client choice is required first.
    await chooseOption("Client", "Harness");

    // Only that Client's Offices are offered.
    await userEvent.click(await screen.findByRole("combobox", { name: "Office" }));
    expect(await screen.findAllByRole("option")).toHaveLength(2);
    await userEvent.click(screen.getByRole("option", { name: "Harness-1317" }));

    // The Office has two Floors, so the Floor selector appears with them.
    await userEvent.click(await screen.findByRole("combobox", { name: /Floor\(s\)/ }));
    expect(await screen.findByRole("option", { name: "3F" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("option", { name: "2F" }));

    await chooseIssue("AC not cooling");
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    expect(createTicket).toHaveBeenCalledWith({
      client_office_id: harnessMainOffice.id,
      issue_ids: [acNotCooling.id],
      floor_ids: [102],
    });
    expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ id: 77 }));
  });

  it("limits Issues to the first selected Issue's Department and disables other Quick Issues", async () => {
    const searchIssues = vi.mocked(referenceDataApi.searchIssues);
    renderForm("CLIENT");
    await chooseOption("Client", "Harness");
    await chooseOption("Office", "Harness-1317");

    const quickIssueGroup = await screen.findByRole("group", { name: "Quick Issues - tap to autofill" });
    expect(within(quickIssueGroup).getByRole("button", { name: "Internet not working" })).not.toHaveAttribute(
      "aria-disabled",
      "true",
    );

    await userEvent.click(within(quickIssueGroup).getByRole("button", { name: "AC not cooling" }));

    // A Quick Issue from another Department can no longer be chosen...
    expect(within(quickIssueGroup).getByRole("button", { name: "Internet not working" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    // ...and the Issue search is now restricted to the Technical Department.
    await userEvent.click(screen.getByRole("combobox", { name: /Issue\(s\)/ }));
    expect(searchIssues).toHaveBeenLastCalledWith({ search: "", departmentId: technicalDepartment.id }, expect.anything());
    expect(screen.queryByRole("option", { name: "Internet not working" })).not.toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "Lift not working" })).toBeInTheDocument();
  });

  it("shows validation messages and does not submit an incomplete form", async () => {
    const createTicket = vi.spyOn(ticketsApi, "createTicket");
    renderForm("CLIENT");
    await chooseOption("Client", "Harness");
    await chooseOption("Office", "Harness-1317");

    await userEvent.click(await screen.findByRole("button", { name: "Submit" }));

    expect(await screen.findByText("Select at least one issue.")).toBeInTheDocument();
    expect(screen.getByText("Select at least one floor.")).toBeInTheDocument();
    expect(createTicket).not.toHaveBeenCalled();
  });

  it("clears the Office and Issues when the Client changes", async () => {
    renderForm("CLIENT");
    await chooseOption("Client", "Harness");
    await chooseOption("Office", "Harness-1317");
    await chooseIssue("AC not cooling");
    const internetQuickIssue = await screen.findByRole("button", { name: "Internet not working" });
    expect(internetQuickIssue).toHaveAttribute("aria-disabled", "true");

    await chooseOption("Client", "Acme");

    // Acme has a single Office, which is chosen automatically. The earlier Issue is gone,
    // so the Quick Issue it had disabled is available again.
    expect(await screen.findByText("Office: Acme-0410")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Internet not working" })).not.toHaveAttribute("aria-disabled", "true");
  });

  it("attaches no Floor ids for an Office with a single Floor", async () => {
    const createTicket = vi.spyOn(ticketsApi, "createTicket").mockResolvedValue(buildTicketDetail());
    renderForm("CLIENT");
    await chooseOption("Client", "Acme");

    await chooseIssue("AC not cooling");
    expect(screen.queryByRole("combobox", { name: /Floor\(s\)/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    expect(createTicket).toHaveBeenCalledWith({ client_office_id: acmeOffice.id, issue_ids: [acNotCooling.id] });
  });

  it("attaches no Floor ids for an Office without Floors", async () => {
    const createTicket = vi.spyOn(ticketsApi, "createTicket").mockResolvedValue(buildTicketDetail());
    renderForm("CLIENT");
    await chooseOption("Client", "Harness");
    await chooseOption("Office", "HSR-1317");

    await chooseIssue("AC not cooling");
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    expect(createTicket).toHaveBeenCalledWith({ client_office_id: harnessHsrOffice.id, issue_ids: [acNotCooling.id] });
  });

  it("requires a description from internal employees but not from Clients", async () => {
    const createTicket = vi.spyOn(ticketsApi, "createTicket").mockResolvedValue(buildTicketDetail());
    renderForm("FACILITY_MANAGER");
    await chooseOption("Client", "Acme");
    await chooseIssue("AC not cooling");

    await userEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(await screen.findByText("Describe the issue.")).toBeInTheDocument();
    expect(createTicket).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText(/Description/), "  Warm air on the 4th floor.  ");
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    expect(createTicket).toHaveBeenCalledWith({
      client_office_id: acmeOffice.id,
      issue_ids: [acNotCooling.id],
      description: "Warm air on the 4th floor.",
    });
  });

  it("shows the API's field and form-level validation errors", async () => {
    vi.spyOn(ticketsApi, "createTicket").mockRejectedValue(
      Object.assign(new Error("Request failed"), {
        isAxiosError: true,
        response: {
          status: 400,
          data: {
            error: {
              code: "VALIDATION_ERROR",
              message: "Invalid request.",
              details: {
                issue_ids: ["Issues cannot belong to multiple departments."],
                non_field_errors: ["Something else is wrong."],
              },
            },
          },
        },
      }),
    );
    renderForm("CLIENT");
    await chooseOption("Client", "Acme");
    await chooseIssue("AC not cooling");

    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    expect(await screen.findByText("Issues cannot belong to multiple departments.")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Something else is wrong.");
  });

  it("explains when the user is not linked to any client", async () => {
    vi.spyOn(referenceDataApi, "getMyClients").mockResolvedValue([]);
    renderForm("CLIENT");

    expect(await screen.findByText("You are not linked to any client, so you cannot create tickets.")).toBeInTheDocument();
  });
});
