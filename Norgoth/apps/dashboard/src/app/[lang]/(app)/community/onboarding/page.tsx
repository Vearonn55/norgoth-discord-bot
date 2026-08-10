import { notFound } from "next/navigation";
import { MemberVerificationView } from "@/components/verification/member-verification-view";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function OnboardingPage({
  params,
}: PageProps<"/[lang]/community/onboarding">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);

  return <MemberVerificationView />;
}
