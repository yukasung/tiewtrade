// jsdom lacks these browser APIs; real browser geometry/focus is checked in E2E.
// Node-only isolation tests intentionally have no DOM.
if (typeof window !== "undefined") {
  Object.defineProperty(window, "matchMedia", { configurable: true, writable: true, value: (query: string): MediaQueryList => {
    const listeners = new Map<EventListenerOrEventListenerObject, EventListener>();
    let previous = window.innerWidth >= 1280;
    return {
      get matches() { return window.innerWidth >= 1280; }, media: query, onchange: null,
      addEventListener(_type: string, listener: EventListenerOrEventListenerObject | null) {
        if (!listener) return;
        const resize = () => {
          const matches = window.innerWidth >= 1280;
          if (matches === previous) return;
          previous = matches;
          const event = new Event("change");
          if (typeof listener === "function") listener(event); else listener.handleEvent(event);
        };
        listeners.set(listener, resize);
        window.addEventListener("resize", resize);
      },
      removeEventListener(_type: string, listener: EventListenerOrEventListenerObject | null) {
        if (!listener) return;
        const resize = listeners.get(listener);
        if (resize) window.removeEventListener("resize", resize);
        listeners.delete(listener);
      },
      addListener() {}, removeListener() {}, dispatchEvent() { return true; },
    };
  } });
  class TestResizeObserver {
    observe() {} unobserve() {} disconnect() {}
  }
  Object.defineProperty(window, "ResizeObserver", { configurable: true, writable: true, value: TestResizeObserver });
}
