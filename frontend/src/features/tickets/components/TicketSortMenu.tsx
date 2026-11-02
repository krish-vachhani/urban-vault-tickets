import SortIcon from "@mui/icons-material/Sort";
import Button from "@mui/material/Button";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import { useState } from "react";

import type { TicketOrdering } from "../types/ticket.types";

type TicketSortMenuProps = {
  ordering: TicketOrdering;
  onChange: (ordering: TicketOrdering) => void;
};

const SORT_CHOICES: { ordering: TicketOrdering; label: string }[] = [
  { ordering: "-created_at", label: "Newest First" },
  { ordering: "created_at", label: "Older First" },
];

/** Created Time sorting, the only sort the assignment requires. */
export function TicketSortMenu({ ordering, onChange }: TicketSortMenuProps) {
  const [anchorElement, setAnchorElement] = useState<HTMLElement | null>(null);

  function choose(newOrdering: TicketOrdering) {
    setAnchorElement(null);
    onChange(newOrdering);
  }

  return (
    <>
      <Button
        variant="outlined"
        startIcon={<SortIcon />}
        aria-haspopup="menu"
        onClick={(event) => setAnchorElement(event.currentTarget)}
      >
        Sort
      </Button>
      <Menu anchorEl={anchorElement} open={anchorElement !== null} onClose={() => setAnchorElement(null)}>
        {SORT_CHOICES.map((choice) => (
          <MenuItem key={choice.ordering} selected={choice.ordering === ordering} onClick={() => choose(choice.ordering)}>
            {choice.label}
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}
