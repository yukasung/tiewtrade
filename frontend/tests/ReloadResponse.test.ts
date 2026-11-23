import { describe, expect, it, vi } from "vitest";
import type { Page, Request, Response } from "@playwright/test";
import { reloadResponse } from "../e2e/helpers/reloadResponse";

describe("reload response ownership", () => {
  it("ignores old responses before and after navigation and accepts a request from the reload", async () => {
    const frame = {};
    let observe!: (request: Request) => void;
    let accept!: (response: Response) => boolean;
    let resolve!: (response: Response) => void;
    const request = (navigation = false, owner = frame) => ({
      isNavigationRequest: () => navigation, frame: () => owner,
    }) as unknown as Request;
    const response = (value: Request) => ({ request: () => value }) as Response;
    const oldRequest = request();
    const current = response(request());
    const off = vi.fn();
    const page = {
      mainFrame: () => frame,
      on: vi.fn((_event: string, listener: (request: Request) => void) => { observe = listener; }),
      off,
      waitForResponse: (predicate: typeof accept) => {
        accept = predicate;
        return new Promise<Response>(done => { resolve = done; });
      },
      reload: () => {
        expect(accept(response(oldRequest))).toBe(false);
        observe(request(true, {})); // A subframe must not start the new scope.
        expect(accept(response(oldRequest))).toBe(false);
        observe(request(true));
        expect(accept(response(oldRequest))).toBe(false);
        observe(current.request());
        expect(accept(current)).toBe(true);
        resolve(current);
        return Promise.resolve(undefined);
      },
    } as unknown as Page;
    expect(await reloadResponse(page, () => true, () => Promise.resolve(undefined))).toBe(current);
    expect(off).toHaveBeenCalledWith("request", observe);
  });

  it("removes its request listener if reload fails", async () => {
    const failure = new Error("navigation failed");
    const off = vi.fn();
    const page = {
      on: vi.fn(), off,
      waitForResponse: () => Promise.reject(failure),
      reload: () => Promise.reject(failure),
    } as unknown as Page;
    await expect(reloadResponse(page, () => true, () => Promise.resolve(undefined))).rejects.toBe(failure);
    expect(off).toHaveBeenCalledWith("request", expect.any(Function));
  });
});
