import { Card } from "@/components/ui/card";

type ValidationStatCardProps = {
  label: string;
  value: string | number;
  tone?: "default" | "danger" | "success" | "warning" | "info";
};

const toneClasses: Record<
  NonNullable<ValidationStatCardProps["tone"]>,
  string
> = {
  default: "",
  danger: "text-danger",
  success: "text-success",
  warning: "text-warning",
  info: "text-info",
};

export function ValidationStatCard({
  label,
  value,
  tone = "default",
}: ValidationStatCardProps) {
  return (
    <Card>
      <div className="small text-body-secondary">{label}</div>
      <div className={`mt-1 display-6 fs-3 fw-semibold ${toneClasses[tone]}`}>
        {value}
      </div>
    </Card>
  );
}
