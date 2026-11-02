import SearchIcon from "@mui/icons-material/Search";
import InputAdornment from "@mui/material/InputAdornment";
import TextField from "@mui/material/TextField";
import { useEffect, useRef, useState, type ChangeEvent } from "react";

const SEARCH_DEBOUNCE_MS = 400;

type TicketSearchFieldProps = {
  /** The search text currently in the URL. */
  value: string;
  onSearch: (searchText: string) => void;
};

/** Search box that updates the URL shortly after typing stops, so each keystroke is not a request. */
export function TicketSearchField({ value, onSearch }: TicketSearchFieldProps) {
  const [typedText, setTypedText] = useState(value);
  const [lastSeenUrlValue, setLastSeenUrlValue] = useState(value);
  const debounceTimer = useRef<number | undefined>(undefined);

  // The timer fires after a delay, by which time the URL may have changed (e.g. another tab was
  // chosen). Calling the newest `onSearch` keeps that change instead of overwriting it.
  const latestOnSearch = useRef(onSearch);
  useEffect(() => {
    latestOnSearch.current = onSearch;
  }, [onSearch]);

  // The URL can change without typing (Back button, "Clear filters"); follow it.
  if (value !== lastSeenUrlValue) {
    setLastSeenUrlValue(value);
    setTypedText(value);
  }

  useEffect(() => () => window.clearTimeout(debounceTimer.current), []);

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const newText = event.target.value;
    setTypedText(newText);
    window.clearTimeout(debounceTimer.current);
    debounceTimer.current = window.setTimeout(() => latestOnSearch.current(newText.trim()), SEARCH_DEBOUNCE_MS);
  }

  return (
    <TextField
      type="search"
      size="small"
      label="Search issues"
      value={typedText}
      onChange={handleChange}
      className="min-w-48 grow"
      slotProps={{
        input: {
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon fontSize="small" />
            </InputAdornment>
          ),
        },
      }}
    />
  );
}
