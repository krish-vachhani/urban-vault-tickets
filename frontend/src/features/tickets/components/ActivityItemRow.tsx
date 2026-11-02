import Avatar from "@mui/material/Avatar";
import Typography from "@mui/material/Typography";

import { formatDateTime } from "../../../shared/utils/formatDateTime";
import type { ActivityItem } from "../types/ticket.types";

type ActivityItemRowProps = {
  item: ActivityItem;
};

const SYSTEM_ACTOR_NAME = "System";

function getInitials(name: string): string {
  return name
    .split(" ")
    .filter((namePart) => namePart.length > 0)
    .slice(0, 2)
    .map((namePart) => namePart.charAt(0).toUpperCase())
    .join("");
}

/** One Activity entry: who did what and when, with the History (`from → to`) and any note underneath. */
export function ActivityItemRow({ item }: ActivityItemRowProps) {
  const actorName = item.actor?.name ?? SYSTEM_ACTOR_NAME;
  const actorLabel = item.actor ? `${item.actor.name} (${item.actor.role_label})` : SYSTEM_ACTOR_NAME;

  return (
    <li className="flex gap-3">
      <Avatar className="h-8 w-8 text-sm" aria-hidden>
        {getInitials(actorName)}
      </Avatar>
      <div className="flex min-w-0 flex-col gap-1">
        <Typography variant="body2">
          <strong>{actorLabel}</strong> {item.type === "ACTION" ? item.description : "commented"}{" "}
          <Typography component="time" variant="caption" color="text.secondary" dateTime={item.created_at}>
            {formatDateTime(item.created_at)}
          </Typography>
        </Typography>
        {item.type === "COMMENT" && (
          <Typography variant="body2" className="rounded-lg bg-neutral-100 p-2 break-words whitespace-pre-wrap">
            {item.description}
          </Typography>
        )}
        {item.change && (
          <Typography variant="body2" color="text.secondary">
            History: {item.change.from} → {item.change.to}
          </Typography>
        )}
        {item.note && (
          <Typography variant="body2" color="text.secondary">
            Forwarding note: {item.note}
          </Typography>
        )}
      </div>
    </li>
  );
}
