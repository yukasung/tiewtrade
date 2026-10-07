import { useState } from "react";
import { DownloadIcon, TrashBinIcon } from "../../../icons";
import {
  ActionRow,
  DangerButton,
  SecondaryButton,
  SelectControl,
  SettingsCard,
  SettingsPanel,
  SettingsSection,
  ToggleRow,
} from "../shared";

export function DataControlPanel() {
  const [retention, setRetention] = useState("90 Days");

  return (
    <SettingsPanel title="Data Control">
      <SettingsSection title="Privacy">
        <SettingsCard>
          <ActionRow
            title="Data retention"
            description="How long to keep your conversations"
            action={
              <SelectControl
                value={retention}
                onChange={setRetention}
                options={[
                  "All Time",
                  "30 Days",
                  "90 Days",
                  "180 Days",
                  "1 year",
                ]}
                size="sm"
              />
            }
          />
          <ToggleRow
            title="Improve models with my data"
            description="Opt in to training on anonymized chats."
          />
          <ToggleRow
            title="Location"
            description="When on, AI uses your location for local info."
            isLast
          />
        </SettingsCard>
      </SettingsSection>

      <SettingsSection title="Export & Delete">
        <SettingsCard>
          <ActionRow
            title="Export user data"
            description="Download a ZIP of all chats and files."
            action={
              <SecondaryButton icon={<DownloadIcon className="size-5" />}>
                Request Export
              </SecondaryButton>
            }
          />
          <ActionRow
            title="Delete all chat"
            description="Permanently remove the entire chats"
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
