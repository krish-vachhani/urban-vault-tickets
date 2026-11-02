import { useQueryClient } from "@tanstack/react-query";
import Alert from "@mui/material/Alert";
import Chip from "@mui/material/Chip";
import Pagination from "@mui/material/Pagination";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import { useState } from "react";

import { ErrorMessage } from "../../../shared/components/ErrorMessage";
import { LoadingIndicator } from "../../../shared/components/LoadingIndicator";
import { ACTIVITY_PAGE_SIZE, ticketActivityQueryOptions, useTicketActivities } from "../hooks/useTicketActivities";
import type { ActivityFilter } from "../types/ticket.types";
import { ActivityItemRow } from "./ActivityItemRow";
import { CommentForm } from "./CommentForm";

type TicketActivityProps = {
  ticketId: number;
};

const FILTER_CHOICES: { filter: ActivityFilter; label: string }[] = [
  { filter: "ALL", label: "All" },
  { filter: "ACTIONS", label: "Actions" },
  { filter: "COMMENTS", label: "Comments" },
];

/** The ticket's Activity feed (oldest first) with its filter chips, plus the pinned comment box. */
export function TicketActivity({ ticketId }: TicketActivityProps) {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<ActivityFilter>("ALL");
  const [page, setPage] = useState(1);
  const [commentPosted, setCommentPosted] = useState(false);
  const activitiesQuery = useTicketActivities(ticketId, filter, page);

  const eventCount = activitiesQuery.data?.count ?? 0;
  const pageCount = Math.max(1, Math.ceil(eventCount / ACTIVITY_PAGE_SIZE));
  const isShowingPlaceholder = activitiesQuery.isPlaceholderData;

  function chooseFilter(newFilter: ActivityFilter) {
    setFilter(newFilter);
    setPage(1);
  }

  // A new comment is the newest event, so show the last page of the full feed.
  async function showNewComment() {
    setCommentPosted(true);
    setFilter("ALL");
    try {
      // A filtered count (or cached All count) cannot locate the newly saved comment.
      const fullFeed = await queryClient.fetchQuery({
        ...ticketActivityQueryOptions(ticketId, "ALL", 1),
        staleTime: 0,
      });
      setPage(Math.max(1, Math.ceil(fullFeed.count / ACTIVITY_PAGE_SIZE)));
    } catch {
      // The comment is already saved. Show the normal feed error/Retry without resubmitting it.
      setPage(1);
    }
  }

  function renderFeed() {
    if (activitiesQuery.isPending) {
      return <LoadingIndicator label="Loading activity" />;
    }
    if (activitiesQuery.isError) {
      return (
        <ErrorMessage
          error={activitiesQuery.error}
          title="Could not load the activity."
          onRetry={() => void activitiesQuery.refetch()}
        />
      );
    }
    if (activitiesQuery.data.results.length === 0) {
      return <Typography color="text.secondary">Nothing to show for this filter yet.</Typography>;
    }
    return (
      <ol className="m-0 flex list-none flex-col gap-4 p-0" aria-busy={isShowingPlaceholder}>
        {activitiesQuery.data.results.map((item) => (
          <ActivityItemRow key={item.id} item={item} />
        ))}
      </ol>
    );
  }

  return (
    <>
      <Paper component="section" aria-labelledby="activity-heading" variant="outlined" className="flex flex-col gap-3 p-3">
        {commentPosted && (
          <Alert severity="success" onClose={() => setCommentPosted(false)}>
            Comment posted.
          </Alert>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <Typography id="activity-heading" component="h2" variant="subtitle1" className="font-semibold">
            Activity
          </Typography>
          <div role="group" aria-label="Filter activity" className="flex gap-1">
            {FILTER_CHOICES.map((choice) => (
              <Chip
                key={choice.filter}
                label={choice.label}
                size="small"
                color={choice.filter === filter ? "primary" : "default"}
                variant={choice.filter === filter ? "filled" : "outlined"}
                aria-pressed={choice.filter === filter}
                onClick={() => chooseFilter(choice.filter)}
              />
            ))}
          </div>
          {activitiesQuery.data && (
            <Typography variant="body2" color="text.secondary" role="status">
              {eventCount} {eventCount === 1 ? "event" : "events"}
            </Typography>
          )}
        </div>
        {renderFeed()}
        {pageCount > 1 && (
          <Pagination
            count={pageCount}
            page={page}
            disabled={isShowingPlaceholder}
            onChange={(_event, newPage) => setPage(newPage)}
            size="small"
          />
        )}
      </Paper>
      <CommentForm ticketId={ticketId} onCommentPosted={showNewComment} />
    </>
  );
}
