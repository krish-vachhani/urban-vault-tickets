import CircularProgress from "@mui/material/CircularProgress";

type LoadingIndicatorProps = {
  label: string;
};

/** Centered spinner announced to screen readers through its accessible label. */
export function LoadingIndicator({ label }: LoadingIndicatorProps) {
  return (
    <div className="flex justify-center p-8">
      <CircularProgress aria-label={label} />
    </div>
  );
}
