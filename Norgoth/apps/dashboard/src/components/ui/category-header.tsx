import type { ReactNode } from "react";
import type { NorgothCategory } from "@/lib/design/category";
import { CATEGORY_TOKENS, categoryAccent } from "@/lib/design/category";

type CategoryHeaderProps = {
  title: string;
  description?: string;
  category: NorgothCategory;
  icon?: ReactNode;
  actions?: ReactNode;
  className?: string;
  as?: "h2" | "h3" | "h4";
};

export function CategoryHeader({
  title,
  description,
  category,
  icon,
  actions,
  className,
  as = "h2",
}: CategoryHeaderProps) {
  const Heading = as;
  const tokens = CATEGORY_TOKENS[category];

  return (
    <div
      className={["norgoth-category-header d-flex flex-wrap align-items-start justify-content-between gap-3 mb-3", className]
        .filter(Boolean)
        .join(" ")}
      style={{ borderLeftColor: categoryAccent(category) }}
      data-category={category}
    >
      <div className="d-flex align-items-start gap-3 min-w-0">
        {icon ? (
          <div
            className="norgoth-category-header-icon flex-shrink-0"
            style={{
              color: categoryAccent(category),
              borderColor: categoryAccent(category),
            }}
            aria-hidden
          >
            {icon}
          </div>
        ) : null}
        <div className="min-w-0">
          <div className="small text-uppercase fw-semibold mb-1" style={{ color: categoryAccent(category) }}>
            {tokens.label}
          </div>
          <Heading className="h5 mb-0 fw-semibold text-white">{title}</Heading>
          {description ? (
            <p className="mb-0 mt-1 small text-body-secondary">{description}</p>
          ) : null}
        </div>
      </div>
      {actions ? (
        <div className="d-flex flex-wrap align-items-center gap-2">{actions}</div>
      ) : null}
    </div>
  );
}
