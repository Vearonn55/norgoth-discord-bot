import { Button } from "@/components/ui/button";
import type { LandingCopy } from "@/components/landing/landing-copy";

export function LandingCtas({
  copy,
  loginHref,
  inviteHref,
  size = "lg",
}: {
  copy: LandingCopy;
  loginHref: string;
  inviteHref: string;
  size?: "md" | "lg";
}) {
  const loginLabel = loginHref.endsWith("/servers")
    ? copy.openCommandCenter
    : copy.login;

  return (
    <div className="norgoth-landing-ctas">
      <Button asChild variant="primary" size={size}>
        <a href={inviteHref}>{copy.addToDiscord}</a>
      </Button>
      <Button asChild variant="secondary" size={size}>
        <a href={loginHref}>{loginLabel}</a>
      </Button>
    </div>
  );
}
