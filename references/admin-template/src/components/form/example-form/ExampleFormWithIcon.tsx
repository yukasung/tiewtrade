import ComponentCard from "@/components/common/ComponentCard";
import Form from "@/components/form/Form";
import Checkbox from "@/components/form/input/Checkbox";
import Input from "@/components/form/input/InputField";
import Label from "@/components/form/Label";
import Button from "@/components/ui/button/Button";
import { ArrowRightIcon, EnvelopeIcon, LockIcon, UserIcon } from "@/icons";
import { cn } from "@/utils";
import { useState } from "react";

export default function ExampleFormWithIcon() {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log("Form submitted:");
  };

  const [isChecked, setIsChecked] = useState(false);
  return (
    <ComponentCard title="Example Form With Icons">
      <Form onSubmit={handleSubmit}>
        <div className="grid grid-cols-1 gap-6">
          <div className="relative">
            <Input
              type="text"
              placeholder="Username"
              id="username"
              className="ps-11"
            />
            <span className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-gray-500 dark:text-gray-400">
              <UserIcon className="size-5" />
            </span>
          </div>
          <div className="relative">
            <Input
              type="text"
              placeholder="Email Address"
              id="email"
              className="ps-11"
            />
            <span className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-gray-500 dark:text-gray-400">
              <EnvelopeIcon className="size-5" />
            </span>
          </div>
          <div className="relative">
            <Input
              type="password"
              placeholder="Password"
              id="password"
              className="ps-11"
            />
            <span className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-gray-500 dark:text-gray-400">
              <LockIcon className="size-5" />
            </span>
          </div>
          <div className="relative">
            <Input
              type="password"
              placeholder="Confirm Password"
              id="confirm-password"
              className="ps-11"
            />
            <span className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-gray-500 dark:text-gray-400">
              <LockIcon className="size-5" />
            </span>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Checkbox
                id="remember-me"
                checked={isChecked}
                onChange={setIsChecked}
              />
              <Label htmlFor="remember-me" className="mb-0">
                Remember me
              </Label>
            </div>
            <div>
              <Button
                size="sm"
                className={cn("inline-flex items-center gap-2")}
              >
                Create Account
                <ArrowRightIcon className="size-5 rtl:rotate-180" />
              </Button>
            </div>
          </div>
        </div>
      </Form>
    </ComponentCard>
  );
}
