import { notFound } from "next/navigation";
import { AutoRoleView } from "@/components/automation/auto-role-view";
import { hasLocale } from "../../../dictionaries";

export default async function AutoRolePage({
  params,
}: PageProps<"/[lang]/automation/auto-role">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  return <AutoRoleView />;
}
