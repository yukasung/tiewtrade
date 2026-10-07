import Label from "@/components/form/Label";
import Input from "@/components/form/input/InputField";
import { ChevronLeftIcon } from "@/icons";
import { cn } from "@/utils";
import { Link } from "react-router";

export default function ResetPasswordForm() {
  return (
    <div className={cn("flex w-full flex-1 flex-col lg:w-1/2")}>
      <div className={cn("mx-auto w-full max-w-md pt-10")}>
        <Link
          to="/"
          className={cn(
            "inline-flex items-center text-sm text-gray-500 transition-colors hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300",
          )}
        >
          <ChevronLeftIcon className="size-5 rtl:rotate-180" />
          Back to dashboard
        </Link>
      </div>
      <div
        className={cn(
          "mx-auto flex w-full max-w-md flex-1 flex-col justify-center",
        )}
      >
        <div className={cn("mb-5 sm:mb-8")}>
          <h1
            className={cn(
              "mb-2 text-title-sm font-semibold text-gray-800 sm:text-title-md dark:text-white/90",
            )}
          >
            Forgot Your Password?
          </h1>
          <p className={cn("text-sm text-gray-500 dark:text-gray-400")}>
            Enter the email address linked to your account, and we’ll send you a
            link to reset your password.
          </p>
        </div>
        <div>
          <form>
            <div className={cn("space-y-5")}>
              {/* <!-- Email --> */}
              <div>
                <Label>
                  Email<span className="text-error-500">*</span>
                </Label>
                <Input
                  type="email"
                  id="email"
                  name="email"
                  placeholder="Enter your email"
                />
              </div>

              {/* <!-- Button --> */}
              <div>
                <button
                  className={cn(
                    "flex w-full items-center justify-center rounded-lg bg-brand-500 px-4 py-3 text-sm font-medium text-white shadow-theme-xs transition hover:bg-brand-600",
                  )}
                >
                  Send Reset Link
                </button>
              </div>
            </div>
          </form>
          <div className={cn("mt-5")}>
            <p
              className={cn(
                "text-center text-sm font-normal text-gray-700 sm:text-start dark:text-gray-400",
              )}
            >
              Wait, I remember my password...
              <Link
                to="/"
                className={cn(
                  "text-brand-500 hover:text-brand-600 dark:text-brand-400",
                )}
              >
                Click here
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
