import { KeyIcon, PlusAltIcon } from "../../../icons";
import {
  ActionRow,
  AppAvatar,
  DangerButton,
  SecondaryButton,
  SettingsCard,
  SettingsPanel,
  SettingsSection,
} from "../shared";

const apps = [
  {
    name: "Google Drive",
    description: "Sync files and collaborate seamlessly with your team.",
    initials: "GD",
    image: "/images/integration/google-drive.svg",
    connected: true,
  },
  {
    name: "Github",
    description: "Automate workflows by connecting apps and services.",
    initials: "GH",
    image: "/images/integration/github.svg",
    darkImage: "/images/integration/github-dark.svg",
    connected: false,
  },
  {
    name: "Calendar",
    description: "Manage events, and optimize your time.",
    initials: "CA",
    image: "/images/integration/calendar.svg",
    connected: false,
  },
  {
    name: "Slack",
    description:
      "Integrate Slack to simplify communication and enhance teamwork.",
    initials: "SL",
    image: "/images/integration/slack.svg",
    connected: false,
  },
];

export function ConnectorPanel() {
  return (
    <SettingsPanel title="Connector">
      <SettingsSection title="Apps">
        <SettingsCard>
          {apps.map((app, index) => (
            <ActionRow
              key={app.name}
              title={app.name}
              description={app.description}
              leading={
                <AppAvatar
                  label={app.name}
                  image={app.image}
                  darkImage={app.darkImage}
                />
              }
              action={
                app.connected ? (
                  <DangerButton>Disconnect</DangerButton>
                ) : (
                  <SecondaryButton icon={<PlusAltIcon className="size-5" />}>
                    Connect
                  </SecondaryButton>
                )
              }
              badge={
                app.connected ? (
                  <span className="inline-flex items-center justify-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-600 dark:bg-green-500/15 dark:text-green-400">
                    Connected
                  </span>
                ) : undefined
              }
              isLast={index === apps.length - 1}
            />
          ))}
        </SettingsCard>
      </SettingsSection>

      <SettingsSection title="API Keys">
        <SettingsCard>
          <ActionRow
            title="Production key"
            description="lk_live_************42ab"
            action={
              <div className="flex  items-center gap-2">
                <SecondaryButton icon={<KeyIcon className="size-5" />}>
                  Rotate
                </SecondaryButton>
                <DangerButton>Revoke</DangerButton>
              </div>
            }
          />
          <ActionRow
            title="Generate new key"
            action={
              <SecondaryButton icon={<PlusAltIcon className="size-5" />}>
                New key
              </SecondaryButton>
            }
            isLast
          />
        </SettingsCard>
      </SettingsSection>
    </SettingsPanel>
  );
}
