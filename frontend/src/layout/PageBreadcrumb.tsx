import { accountText as t } from "../accountMessages";
import { navigateAccountPage } from "../accountNavigation";

/** Adapted from references/admin-template/src/components/common/PageBreadCrumb.tsx. */
export function PageBreadcrumb({ title }: { title: string }) {
  return <div className="page-breadcrumb flex flex-wrap items-center justify-between gap-3 mb-6">
    <h1 className="text-xl font-semibold">{title}</h1>
    <nav aria-label={t("breadcrumb")}><ol className="flex items-center gap-1.5">
      <li><a href="/chart" onClick={navigateAccountPage}>{t("home")}</a></li>
      <li aria-hidden="true">›</li>
      <li aria-current="page">{title}</li>
    </ol></nav>
  </div>;
}
