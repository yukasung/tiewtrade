import Label from "@/components/form/Label";
import Input from "@/components/form/input/InputField";
import Button from "@/components/ui/button/Button";
import { Modal } from "@/components/ui/modal";
import { useModal } from "@/hooks/useModal";
import { PlusIcon } from "@/icons";
import { cn } from "@/utils";

interface AddApiKeyModalProps {
  className?: string;
}

export default function AddApiKeyModal({ className }: AddApiKeyModalProps) {
  const addApiKeyModal = useModal();
  return (
    <>
      <Button
        onClick={addApiKeyModal.openModal}
        startIcon={<PlusIcon className="size-5" />}
        className={cn(className)}
      >
        Add API Key
      </Button>
      <Modal
        isOpen={addApiKeyModal.isOpen}
        onClose={addApiKeyModal.closeModal}
        className={cn(
          "relative w-full max-w-[600px] rounded-3xl bg-white p-6 sm:m-0 lg:p-10 dark:bg-gray-900",
        )}
      >
        <div>
          <h4 className="mb-1 text-start text-title-sm font-semibold text-gray-800 dark:text-white/90">
            Generate API key
          </h4>
          <p className="mb-7 text-start text-sm leading-6 text-gray-500 dark:text-gray-400">
            To enable secure access to the web services, your app requires an
            API key with permissions for resources such as the S3 bucket.
          </p>
          <form action="#" onSubmit={(e) => e.preventDefault()}>
            <div>
              <Label className="text-start">Enter your application name</Label>
              <Input type="text" value="Saasbold" />
            </div>
            <p className="mt-4 text-start text-sm text-gray-500 dark:text-gray-400">
              Naming your application makes it easier to recognize your API key
              in the future.
            </p>
          </form>
          <div className="mt-8 flex w-full flex-col items-center justify-between gap-3 sm:flex-row">
            <Button
              variant="outline"
              className="w-full"
              onClick={addApiKeyModal.closeModal}
            >
              Close
            </Button>
            <Button className="w-full">Generate API key</Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
