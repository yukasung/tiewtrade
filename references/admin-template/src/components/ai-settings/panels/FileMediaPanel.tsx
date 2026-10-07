import { useState } from "react";
import {
  ActionRow,
  RangeControl,
  SelectControl,
  SettingsCard,
  SettingsPanel,
  SettingsSection,
} from "../shared";

const allowedFormats = ["PNG", "JPG", "PDF", "MP4", "MD", "ZIP"];

export function FileMediaPanel() {
  const [maxFileSize, setMaxFileSize] = useState(20);
  const [compressionQuality, setCompressionQuality] = useState(60);
  const [exportFormat, setExportFormat] = useState("PNG");

  return (
    <SettingsPanel title="File & Media">
      <SettingsSection title="Upload Settings">
        <SettingsCard>
          <ActionRow
            title="Max file size"
            description="Maximum upload size (50 MB)."
            action={
              <RangeControl value={maxFileSize} onChange={setMaxFileSize} />
            }
          />
          <ActionRow
            title="Allowed formats"
            action={
              <div className="flex flex-wrap items-center gap-2">
                {allowedFormats.map((format) => (
                  <span
                    key={format}
                    className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-normal text-gray-500 dark:bg-gray-800 dark:text-gray-400"
                  >
                    {format}
                  </span>
                ))}
              </div>
            }
            isLast
          />
        </SettingsCard>
      </SettingsSection>

      <SettingsSection title="Export Settings">
        <SettingsCard>
          <ActionRow
            title="Default export format"
            action={
              <SelectControl
                value={exportFormat}
                onChange={setExportFormat}
                options={["PNG", "JPEG", "PDF", "WEBP"]}
                size="sm"
              />
            }
          />
          <ActionRow
            title="Compression quality"
            action={
              <RangeControl
                value={compressionQuality}
                onChange={setCompressionQuality}
              />
            }
            isLast
          />
        </SettingsCard>
      </SettingsSection>
    </SettingsPanel>
  );
}
