import { useState } from "react";
import {
  ActionRow,
  Field,
  inputClass,
  RangeControl,
  SegmentedControl,
  SettingsCard,
  SettingsPanel,
  SettingsSection,
  textareaClass,
} from "../shared";

export function PersonalizationPanel() {
  const [tone, setTone] = useState("Concise");
  const [outputLength, setOutputLength] = useState("Short");
  const [creativity, setCreativity] = useState(60);

  return (
    <SettingsPanel title="Personalization">
      <SettingsSection title="AI Behavior">
        <SettingsCard>
          <ActionRow
            title="Response tone"
            action={
              <SegmentedControl
                options={["Concise", "Balanced", "Expressive"]}
                value={tone}
                onChange={setTone}
              />
            }
          />
          <ActionRow
            title="Creativity"
            description="Higher values produce more varied output."
            action={<RangeControl value={creativity} onChange={setCreativity} />}
          />
          <ActionRow
            title="Output length"
            action={
              <SegmentedControl
                options={["Short", "Medium", "Long"]}
                value={outputLength}
                onChange={setOutputLength}
              />
            }
            isLast
          />
        </SettingsCard>
      </SettingsSection>

      <SettingsSection title="Custom Interactions">
        <SettingsCard className="px-5 py-4">
          <p className="mb-3 text-sm font-medium text-gray-800 dark:text-white/90">
            Instructions
          </p>
          <textarea
            rows={4}
            placeholder="Be direct. Skip preamble. Use markdown. Prefer examples over abstractions."
            className={textareaClass}
          />
        </SettingsCard>
      </SettingsSection>

      <SettingsSection title="About You">
        <SettingsCard className="px-5 py-4">
          <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Nickname">
              <input
                type="text"
                placeholder="What should AI call you"
                className={inputClass}
              />
            </Field>
            <Field label="Occupation">
              <input
                type="text"
                placeholder="Software Engineer"
                className={inputClass}
              />
            </Field>
          </div>
          <Field label="More about you">
            <textarea
              rows={3}
              placeholder="Passionate about solving problems and creating value."
              className={textareaClass}
            />
          </Field>
        </SettingsCard>
      </SettingsSection>
    </SettingsPanel>
  );
}
