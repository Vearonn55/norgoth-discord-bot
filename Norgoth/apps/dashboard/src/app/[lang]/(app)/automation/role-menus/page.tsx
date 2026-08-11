import { notFound } from "next/navigation";
import { cilTags } from "@coreui/icons";
import { PageHeader } from "@/components/layout/page-header";
import { Icon } from "@/components/ui/icon";
import { RoleMenusPanel } from "@/components/automation/role-menus-panel";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function RoleMenusPage({
  params,
}: PageProps<"/[lang]/automation/role-menus">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);

  return (
    <div className="d-flex flex-column gap-4">
        <PageHeader
          title="Self-Assignable Roles"
          icon={<Icon icon={cilTags} size="xl" />}
          category="roles"
          description="Publish embeds with toggle buttons so members can pick their own roles."
          infoKey="selfAssignableRoles"
        />

        <RoleMenusPanel />
      </div>
  );
}
