import { useEffect, useRef } from 'react';

declare global {
  interface Window {
    smartCaptcha?: {
      render: (
        container: HTMLElement | string,
        options: { sitekey: string; callback?: (token: string) => void; hl?: string },
      ) => number;
      reset: (widgetId?: number) => void;
      destroy: (widgetId: number) => void;
    };
  }
}

const SITEKEY = import.meta.env.VITE_YANDEX_CAPTCHA_CLIENT_KEY as string | undefined;
export const CAPTCHA_ENABLED = Boolean(SITEKEY);

interface SmartCaptchaProps {
  onToken: (token: string) => void;
}

/**
 * Виджет Яндекс SmartCaptcha. Скрипт подключается в index.html;
 * здесь ждём появления window.smartCaptcha и рендерим виджет.
 */
export default function SmartCaptcha({ onToken }: SmartCaptchaProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const widgetIdRef = useRef<number | null>(null);
  const onTokenRef = useRef(onToken);
  onTokenRef.current = onToken;

  useEffect(() => {
    if (!CAPTCHA_ENABLED) return;

    let attempts = 0;
    const render = () => {
      if (!containerRef.current || !window.smartCaptcha || widgetIdRef.current !== null) return;
      widgetIdRef.current = window.smartCaptcha.render(containerRef.current, {
        sitekey: SITEKEY as string,
        callback: (token: string) => onTokenRef.current(token),
        hl: 'ru',
      });
    };

    render();
    const timer = window.setInterval(() => {
      attempts += 1;
      render();
      if (widgetIdRef.current !== null || attempts > 50) window.clearInterval(timer);
    }, 200);

    return () => {
      window.clearInterval(timer);
      if (widgetIdRef.current !== null) {
        window.smartCaptcha?.destroy(widgetIdRef.current);
        widgetIdRef.current = null;
      }
    };
  }, []);

  if (!CAPTCHA_ENABLED) return null;

  return <div ref={containerRef} className="mb-2" />;
}
