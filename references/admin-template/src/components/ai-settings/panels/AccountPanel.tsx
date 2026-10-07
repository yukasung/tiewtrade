import { LogoutIcon, TrashBinIcon } from "../../../icons";
import {
  ActionRow,
  DangerButton,
  FormRow,
  inputClass,
  PrimaryButton,
  SecondaryButton,
  SettingsCard,
  SettingsPanel,
  SettingsSection,
  ToggleRow,
} from "../shared";

export function AccountPanel() {
  return (
    <SettingsPanel title="Account">
      <SettingsSection title="Profile Info">
        <SettingsCard>
          <div className="flex items-center gap-3 border-b border-gray-100 p-4 dark:border-gray-800">
            <div className="bg-brand-400 inline-flex size-15 items-center justify-center rounded-full text-2xl font-medium text-white">
              M
            </div>
            <div>
              <label className="mb-2 inline-flex h-7 cursor-pointer items-center justify-center rounded-lg border border-gray-300 px-3 py-1 text-sm font-medium text-gray-700 shadow-xs dark:bg-gray-800 hover:bg-gray-100 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-white/90">
                <input type="file" className="hidden" name="avatar" />
                Upload Avatar
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-500">
                Min 400x400px, PNG or JPEG formats.
              </p>
            </div>
          </div>
          <FormRow label="Full Name">
            <input
              type="text"
              placeholder="Musharof Chowdhory"
              className={inputClass}
            />
          </FormRow>
          <FormRow label="Email">
            <input
              type="email"
              placeholder="musharof@example.com"
              className={inputClass}
            />
          </FormRow>
          <FormRow label="Workspace Name">
            <input type="text" placeholder="Pimjo" className={inputClass} />
          </FormRow>
          <div className="flex justify-end p-4">
            <PrimaryButton>Save Changes</PrimaryButton>
          </div>
        </SettingsCard>
      </SettingsSection>

      <SettingsSection title="Security">
        <SettingsCard>
          <ActionRow
            title="Change password"
            description="Last updated 2 months ago"
            action={<SecondaryButton>Update password</SecondaryButton>}
          />
          <ToggleRow
            title="Two-Factor Authentication"
            description="3 devices currently signed in"
          />
          <ActionRow
            title="Active sessions"
            description="3 devices currently signed in"
            action={<SecondaryButton>Manage</SecondaryButton>}
            isLast
          />
        </SettingsCard>
      </SettingsSection>

      <SettingsSection title="Danger Zone">
        <SettingsCard>
          <ActionRow
            title="Logout all devices"
            description="Sign out from every active session."
            action={
              <SecondaryButton icon={<LogoutIcon className="size-5" />}>
                Logout All
              </SecondaryButton>
            }
          />
          <ActionRow
            title="Delete account"
            description="Permanently remove this workspace and all saved data."
            action={
              <DangerButton icon={<TrashBinIcon className="size-5" />}>
                Delete
              </DangerButton>
            }
            isLast
          />
        </SettingsCard>
      </SettingsSection>
    </SettingsPanel>
  );
}
